"""
Session repository managing historical call archives, conversational turn logs,
and latency metrics persisted from Redis into MongoDB.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pymongo.errors import PyMongoError

from schemas.call_session import CallSessionRecord, TurnRecord, CallLatencyMetrics
from schemas.session import SessionData
from services.db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class SessionRepository(BaseRepository):
    """
    Repository for persisting and analyzing telephony and web voice sessions.
    """

    @property
    def collection(self):
        return self._client.call_sessions

    async def archive_session(
        self,
        session: SessionData,
        final_state: Optional[str] = None,
        turns: Optional[List[TurnRecord]] = None,
    ) -> bool:
        """
        Archive an ephemeral Redis SessionData instance into MongoDB call_sessions.
        """
        if not await self.ensure_connected() or self.collection is None:
            return True

        now = datetime.now(timezone.utc)
        turn_logs = turns or []
        
        # Aggregate latencies
        total_asr = session.asr_latency_ms
        total_llm = session.llm_latency_ms
        total_tts = session.tts_latency_ms
        total_vector = session.vector_search_latency_ms
        turns_count = session.turn_count or max(len(turn_logs), 1)

        start_time = session.created_at
        duration = (now - start_time).total_seconds() if start_time else 0.0

        metrics = CallLatencyMetrics(
            total_call_duration_seconds=round(max(duration, 0.0), 2),
            p50_turn_latency_ms=int(session.total_latency_ms / turns_count) if turns_count else 0,
            p95_turn_latency_ms=int(session.total_latency_ms / turns_count * 1.2) if turns_count else 0,
            average_asr_latency_ms=int(total_asr / turns_count) if turns_count else 0,
            average_llm_latency_ms=int(total_llm / turns_count) if turns_count else 0,
            average_vector_search_ms=int(total_vector / turns_count) if turns_count else 0,
        )

        final_slots_map = {
            k: v.value for k, v in session.slots.items() if v.value is not None
        }

        record = CallSessionRecord(
            session_id=session.session_id,
            call_uuid=session.call_uuid,
            phone_hash=session.phone_hash,
            language=session.language,
            dialect=session.dialect,
            final_state=final_state or session.current_state.value,
            turn_count=session.turn_count,
            turns=turn_logs,
            final_slots=final_slots_map,
            recommended_courses=session.recommendations,
            audio_vault_refs=session.audio_vault_refs,
            latency_metrics=metrics,
            error_count=session.error_count,
            start_time=session.created_at,
            end_time=now,
            created_at=now,
        )

        try:
            await self.collection.update_one(
                {"session_id": session.session_id},
                {"$set": record.model_dump()},
                upsert=True,
            )
            logger.info(f"Archived call session {session.session_id} to MongoDB.")
            return True
        except PyMongoError as e:
            logger.error(f"Failed to archive call session {session.session_id}: {e}")
            return False

    async def get_session(self, session_id: str) -> Optional[CallSessionRecord]:
        """Fetch archived call session by ID."""
        if not await self.ensure_connected() or self.collection is None:
            return None

        try:
            doc = await self.collection.find_one({"session_id": session_id})
            if doc:
                return CallSessionRecord.model_validate(doc)
            return None
        except Exception as e:
            logger.error(f"Failed to fetch call session {session_id}: {e}")
            return None

    async def list_recent_sessions(
        self,
        phone_hash: Optional[str] = None,
        limit: int = 10,
    ) -> List[CallSessionRecord]:
        """List recent call sessions, optionally filtered by phone hash."""
        if not await self.ensure_connected() or self.collection is None:
            return []

        query = {"phone_hash": phone_hash} if phone_hash else {}
        try:
            cursor = self.collection.find(query).sort("start_time", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [CallSessionRecord.model_validate(d) for d in docs]
        except Exception as e:
            logger.error(f"Failed to list call sessions: {e}")
            return []
