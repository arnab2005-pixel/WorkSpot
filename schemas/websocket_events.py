"""
WebSocket event schemas for PM-AJAY Voice Assistant.

These define the real-time full-duplex telephony protocol over WebSocket
between FreeSWITCH (via mod_audio_fork) and the media server.
"""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class WSMessageType(str, Enum):
    """WebSocket message types."""

    # Ingress (Client/FreeSWITCH -> Server)
    START_CALL = "START_CALL"
    AUDIO_CHUNK = "AUDIO_CHUNK"
    BARGE_IN = "BARGE_IN"
    HANGUP = "HANGUP"
    DTMF = "DTMF"

    # Egress (Server -> Client/FreeSWITCH)
    CLEAR_BUFFER = "CLEAR_BUFFER"
    TRANSCRIPT_INTERIM = "TRANSCRIPT_INTERIM"
    TRANSCRIPT_FINAL = "TRANSCRIPT_FINAL"
    TTS_CHUNK = "TTS_CHUNK"
    TTS_START = "TTS_START"
    TTS_END = "TTS_END"
    STATE_CHANGE = "STATE_CHANGE"
    ERROR = "ERROR"
    PING = "PING"
    PONG = "PONG"


class WSIncomingMessage(BaseModel):
    """Base model for incoming WebSocket messages."""

    event: WSMessageType
    session_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WSOutgoingMessage(BaseModel):
    """Base model for outgoing WebSocket messages."""

    event: WSMessageType
    session_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# INGRESS EVENTS (FreeSWITCH -> Server)
# ============================================================


class StartCallEvent(WSIncomingMessage):
    """
    Initial event when a call starts.

    Sent by FreeSWITCH via mod_audio_fork when call is answered
    and audio forking begins.
    """

    event: Literal[WSMessageType.START_CALL] = WSMessageType.START_CALL
    caller_id: str = Field(..., description="Caller ID (phone number)")
    call_uuid: str | None = Field(None, description="FreeSWITCH call UUID")
    sample_rate: int = Field(default=8000, description="Audio sample rate (Hz)")
    channels: int = Field(default=1, description="Audio channels")
    codec: str = Field(default="L16", description="Audio codec")
    metadata: dict = Field(default_factory=dict)


class AudioChunkEvent(WSIncomingMessage):
    """
    Raw audio chunk from FreeSWITCH.

    Binary payload: 8kHz 16-bit mono linear PCM.
    Frame size: 20ms = 160 samples = 320 bytes.
    """

    event: Literal[WSMessageType.AUDIO_CHUNK] = WSMessageType.AUDIO_CHUNK
    sequence: int = Field(..., description="Monotonic sequence number")
    audio_data: bytes = Field(..., description="Raw PCM audio data")
    duration_ms: int = Field(default=20, description="Chunk duration in ms")
    is_silence: bool = Field(default=False, description="VAD hint from FreeSWITCH")


class BargeInEvent(WSIncomingMessage):
    """
    Barge-in detected - user started speaking during TTS playback.

    Server should immediately stop TTS and clear audio buffer.
    """

    event: Literal[WSMessageType.BARGE_IN] = WSMessageType.BARGE_IN
    timestamp_ms: int = Field(
        ..., description="Offset in current TTS playback where barge-in occurred"
    )


class HangupEvent(WSIncomingMessage):
    """Call hangup event."""

    event: Literal[WSMessageType.HANGUP] = WSMessageType.HANGUP
    reason: str = Field(default="NORMAL_CLEARING", description="Hangup cause")
    duration_seconds: int | None = None


class DTMFEvent(WSIncomingMessage):
    """DTMF digit received (fallback input)."""

    event: Literal[WSMessageType.DTMF] = WSMessageType.DTMF
    digit: str = Field(..., pattern=r"^[0-9*#]$")
    duration_ms: int = Field(default=100)


# ============================================================
# EGRESS EVENTS (Server -> FreeSWITCH)
# ============================================================


class ClearBufferEvent(WSOutgoingMessage):
    """
    Instruct FreeSWITCH to clear its playout buffer.

    Used on barge-in to stop current TTS playback immediately.
    """

    event: Literal[WSMessageType.CLEAR_BUFFER] = WSMessageType.CLEAR_BUFFER
    reason: str = Field(default="BARGE_IN_DETECTED")


class TranscriptInterimEvent(WSOutgoingMessage):
    """
    Interim (partial) ASR transcript.

    Sent during speech recognition for real-time feedback.
    """

    event: Literal[WSMessageType.TRANSCRIPT_INTERIM] = WSMessageType.TRANSCRIPT_INTERIM
    text: str = Field(..., description="Partial transcript text")
    language: str = Field(default="hi")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    is_final: bool = False


class TranscriptFinalEvent(WSOutgoingMessage):
    """
    Final ASR transcript after speech endpoint detection.

    This triggers the LLM/FSM processing pipeline.
    """

    event: Literal[WSMessageType.TRANSCRIPT_FINAL] = WSMessageType.TRANSCRIPT_FINAL
    text: str = Field(..., description="Final transcript text")
    language: str = Field(default="hi")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    duration_ms: int = Field(default=0, description="Speech duration in ms")
    asr_latency_ms: int = Field(default=0, description="ASR processing latency")
    is_hallucinated: bool = Field(
        default=False, description="Flagged by hallucination protection"
    )


class TTSChunkEvent(WSOutgoingMessage):
    """
    TTS audio chunk for playback.

    Binary payload: 8kHz 16-bit mono linear PCM (downsampled from 22.05kHz).
    Frame size: 20ms = 160 samples = 320 bytes.
    """

    event: Literal[WSMessageType.TTS_CHUNK] = WSMessageType.TTS_CHUNK
    sequence: int = Field(..., description="Chunk sequence number")
    audio_data: bytes = Field(..., description="Raw PCM audio data (8kHz)")
    duration_ms: int = Field(default=20)
    is_first: bool = Field(default=False)
    is_last: bool = Field(default=False)
    text: str | None = Field(None, description="Text this chunk corresponds to")


class TTSStartEvent(WSOutgoingMessage):
    """TTS synthesis started."""

    event: Literal[WSMessageType.TTS_START] = WSMessageType.TTS_START
    text: str = Field(..., description="Full text being synthesized")
    estimated_chunks: int = Field(default=0)


class TTSEndEvent(WSOutgoingMessage):
    """TTS synthesis completed."""

    event: Literal[WSMessageType.TTS_END] = WSMessageType.TTS_END
    total_chunks: int
    total_duration_ms: int
    synthesis_latency_ms: int


class StateChangeEvent(WSOutgoingMessage):
    """FSM state transition notification."""

    event: Literal[WSMessageType.STATE_CHANGE] = WSMessageType.STATE_CHANGE
    from_state: str
    to_state: str
    prompt_text: str | None = None
    missing_slots: list = Field(default_factory=list)


class ErrorEvent(WSOutgoingMessage):
    """Error notification."""

    event: Literal[WSMessageType.ERROR] = WSMessageType.ERROR
    error_code: str
    error_message: str
    recoverable: bool = True
    details: dict = Field(default_factory=dict)


class PingEvent(WSOutgoingMessage):
    """Keepalive ping."""

    event: Literal[WSMessageType.PING] = WSMessageType.PING
    sequence: int


class PongEvent(WSIncomingMessage):
    """Keepalive pong response."""

    event: Literal[WSMessageType.PONG] = WSMessageType.PONG
    sequence: int


# ============================================================
# Union types for message handling
# ============================================================

IncomingEvent = (
    StartCallEvent
    | AudioChunkEvent
    | BargeInEvent
    | HangupEvent
    | DTMFEvent
    | PongEvent
)

OutgoingEvent = (
    ClearBufferEvent
    | TranscriptInterimEvent
    | TranscriptFinalEvent
    | TTSChunkEvent
    | TTSStartEvent
    | TTSEndEvent
    | StateChangeEvent
    | ErrorEvent
    | PingEvent
)

# ============================================================
# Helper functions
# ============================================================


def parse_incoming_message(data: dict) -> IncomingEvent:
    """Parse incoming WebSocket message to appropriate event type."""
    event_type = data.get("event")

    if event_type == WSMessageType.START_CALL:
        return StartCallEvent(**data)
    elif event_type == WSMessageType.AUDIO_CHUNK:
        return AudioChunkEvent(**data)
    elif event_type == WSMessageType.BARGE_IN:
        return BargeInEvent(**data)
    elif event_type == WSMessageType.HANGUP:
        return HangupEvent(**data)
    elif event_type == WSMessageType.DTMF:
        return DTMFEvent(**data)
    elif event_type == WSMessageType.PONG:
        return PongEvent(**data)
    else:
        raise ValueError(f"Unknown incoming event type: {event_type}")


def create_outgoing_event(
    event_type: WSMessageType, session_id: str, **kwargs
) -> OutgoingEvent:
    """Factory for creating outgoing events."""
    base = {"event": event_type, "session_id": session_id}
    base.update(kwargs)

    if event_type == WSMessageType.CLEAR_BUFFER:
        return ClearBufferEvent(**base)
    elif event_type == WSMessageType.TRANSCRIPT_INTERIM:
        return TranscriptInterimEvent(**base)
    elif event_type == WSMessageType.TRANSCRIPT_FINAL:
        return TranscriptFinalEvent(**base)
    elif event_type == WSMessageType.TTS_CHUNK:
        return TTSChunkEvent(**base)
    elif event_type == WSMessageType.TTS_START:
        return TTSStartEvent(**base)
    elif event_type == WSMessageType.TTS_END:
        return TTSEndEvent(**base)
    elif event_type == WSMessageType.STATE_CHANGE:
        return StateChangeEvent(**base)
    elif event_type == WSMessageType.ERROR:
        return ErrorEvent(**base)
    elif event_type == WSMessageType.PING:
        return PingEvent(**base)
    else:
        raise ValueError(f"Unknown outgoing event type: {event_type}")


# ============================================================
# Audio format constants
# ============================================================

# Telephony audio format (FreeSWITCH mod_audio_fork)
TELEPHONY_SAMPLE_RATE = 8000
TELEPHONY_CHANNELS = 1
TELEPHONY_BIT_DEPTH = 16
TELEPHONY_FRAME_MS = 20
TELEPHONY_FRAME_SAMPLES = TELEPHONY_SAMPLE_RATE * TELEPHONY_FRAME_MS // 1000  # 160
TELEPHONY_FRAME_BYTES = (
    TELEPHONY_FRAME_SAMPLES * TELEPHONY_CHANNELS * (TELEPHONY_BIT_DEPTH // 8)
)  # 320

# ASR audio format (Whisper expects 16kHz)
ASR_SAMPLE_RATE = 16000
ASR_FRAME_MS = 20
ASR_FRAME_SAMPLES = ASR_SAMPLE_RATE * ASR_FRAME_MS // 1000  # 320

# TTS native output format (indic-tts FastPitch + HiFi-GAN)
TTS_NATIVE_SAMPLE_RATE = 22050
TTS_FRAME_MS = 20
TTS_FRAME_SAMPLES = TTS_NATIVE_SAMPLE_RATE * TTS_FRAME_MS // 1000  # 441

# VAD window sizes (Silero VAD v5)
VAD_WINDOW_8K = 256  # 32ms at 8kHz
VAD_WINDOW_16K = 512  # 32ms at 16kHz
