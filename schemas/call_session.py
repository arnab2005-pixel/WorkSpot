"""
Call session and audit trail data models for PM-AJAY Voice Assistant.

Represents persisted MongoDB records for telephony/web voice sessions,
including turn-by-turn transcripts, component latencies, and DPDP audit linkages.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TurnLatencyBreakdown(BaseModel):
    """Component-level latency breakdown for a conversational turn (in milliseconds)."""

    vad_ms: int = Field(default=0, ge=0)
    asr_ms: int = Field(default=0, ge=0)
    llm_ms: int = Field(default=0, ge=0)
    tts_ms: int = Field(default=0, ge=0)
    vector_search_ms: int = Field(default=0, ge=0)
    total_turn_ms: int = Field(default=0, ge=0)


class TurnRecord(BaseModel):
    """Single conversational turn record stored in call_sessions."""

    turn_number: int = Field(..., ge=1)
    user_transcript: str = Field(..., description="User input transcribed by ASR")
    detected_dialect: str | None = None
    spoken_response_indic: str = Field(
        ..., description="Spoken assistant response in Hindi/dialect"
    )
    extracted_state: str = Field(..., description="Active FSM state during turn")
    latency: TurnLatencyBreakdown = Field(default_factory=TurnLatencyBreakdown)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CallLatencyMetrics(BaseModel):
    """Aggregated call performance metrics."""

    total_call_duration_seconds: float = Field(default=0.0, ge=0.0)
    p50_turn_latency_ms: int = Field(default=0, ge=0)
    p95_turn_latency_ms: int = Field(default=0, ge=0)
    average_asr_latency_ms: int = Field(default=0, ge=0)
    average_llm_latency_ms: int = Field(default=0, ge=0)
    average_vector_search_ms: int = Field(default=0, ge=0)


class CallSessionRecord(BaseModel):
    """
    Complete call session audit document persisted in MongoDB.
    Archived from ephemeral Redis session data upon call completion or hangup.
    """

    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(
        ..., min_length=1, max_length=64, description="Unique session ID"
    )
    call_uuid: str | None = Field(None, description="FreeSWITCH call UUID")
    phone_hash: str | None = Field(None, description="Salted SHA-256 phone hash")

    # Language & dialect
    language: str = Field(default="hi")
    dialect: str | None = Field(default="bhojpuri_mixed")

    # Final FSM state
    final_state: str = Field(
        ..., description="Terminal state e.g. COMPLETED, HANGUP, ERROR"
    )
    turn_count: int = Field(default=0, ge=0)

    # Detailed turn logs
    turns: list[TurnRecord] = Field(default_factory=list)

    # Final captured profiling slots
    final_slots: dict[str, Any] = Field(default_factory=dict)

    # Recommended NSQF courses delivered during call
    recommended_courses: list[dict[str, Any]] = Field(default_factory=list)

    # Audio vault references (e.g. S3 / GCS URIs)
    audio_vault_refs: list[str] = Field(default_factory=list)

    # Performance metrics
    latency_metrics: CallLatencyMetrics = Field(default_factory=CallLatencyMetrics)

    # Event counters
    error_count: int = Field(default=0, ge=0)
    barge_in_count: int = Field(default=0, ge=0)

    # Timestamps
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
