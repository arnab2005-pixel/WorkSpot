"""
Ephemeral session cache backed by Redis 7.2.
Maintains state machine sessions with automatic TTL expiration (1800s default)
and graceful in-memory fallback when Redis is unavailable.
"""

import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from pydantic import ValidationError

from config.config import get_settings
from schemas.session import SessionData

logger = logging.getLogger(__name__)
settings = get_settings()


class SessionCache:
    """
    Async Redis session cache for LangGraph conversational state.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ):
        self.redis_url = redis_url or settings.redis_url
        self.ttl_seconds = ttl_seconds or settings.session_ttl_seconds
        self._redis: Optional[aioredis.Redis] = None
        self._memory_cache: Dict[str, str] = {}
        self._connected = False

    async def connect(self):
        """Connect to Redis instance."""
        if self._connected and self._redis is not None:
            return
        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                max_connections=settings.redis_max_connections,
                decode_responses=True,
                socket_timeout=2.0,
            )
            await self._redis.ping()
            self._connected = True
            logger.info(f"Connected to Redis session cache at {self.redis_url}")
        except RedisError as exc:
            logger.warning(
                "Redis connection failed: %s. "
                "Falling back to in-memory session cache.",
                exc,
            )
            self._connected = False

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._connected = False

    def _key(self, session_id: str) -> str:
        return f"pm_ajay:session:{session_id}"

    async def save_session(self, session: SessionData) -> bool:
        """Save or update session state."""
        await self.connect()
        key = self._key(session.session_id)
        data_str = session.model_dump_json()

        if self._connected and self._redis:
            try:
                await self._redis.setex(key, self.ttl_seconds, data_str)
                return True
            except RedisError as exc:
                logger.error("Redis setex failed: %s. Falling back to memory.", exc)
                self._memory_cache[key] = data_str
                return True
        else:
            self._memory_cache[key] = data_str
            return True

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Load session data by ID."""
        await self.connect()
        key = self._key(session_id)

        raw_data = None
        if self._connected and self._redis:
            try:
                raw_data = await self._redis.get(key)
            except RedisError as exc:
                logger.error("Redis get failed: %s. Checking memory fallback.", exc)
                raw_data = self._memory_cache.get(key)
        else:
            raw_data = self._memory_cache.get(key)

        if not raw_data:
            return None

        try:
            return SessionData.model_validate_json(raw_data)
        except (ValidationError, ValueError, TypeError) as exc:
            logger.error("Error deserializing session %s: %s", session_id, exc)
            return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete session data on call termination."""
        await self.connect()
        key = self._key(session_id)
        self._memory_cache.pop(key, None)

        if self._connected and self._redis:
            try:
                await self._redis.delete(key)
                return True
            except RedisError as exc:
                logger.error("Redis delete failed: %s", exc)
                return False
        return True
