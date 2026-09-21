"""
Pydantic schemas for PM-AJAY Voice Assistant.
"""

from .beneficiary import (
    Demographics,
    ProfilingSlots,
    ConsentAudit,
    BeneficiaryRecord,
    BeneficiaryCreate,
    BeneficiaryUpdate,
)

from .course import (
    CourseDocument,
    CourseCreate,
    CourseSearchQuery,
    CourseRecommendation,
)

from .session import (
    SessionState,
    SessionData,
    SessionCreate,
    SessionUpdate,
    FSMState,
    SlotStatus,
    ExtractedSlots,
)

from .beneficiary_profile import (
    EnterpriseAspirations,
    ProfileSlots,
    DialogueState,
    ConversationalResponse,
    LLMIntakePayload,
)

from .call_session import (
    CallSessionRecord,
    TurnRecord,
    TurnLatencyBreakdown,
    CallLatencyMetrics,
)

from .lgd_district import (
    LgdDistrictRecord,
)

from .dpiu_application import (
    DpiuApplicationRecord,
)

from .websocket_events import (
    WSMessageType,
    WSIncomingMessage,
    WSOutgoingMessage,
    StartCallEvent,
    HangupEvent,
    TranscriptInterimEvent,
    TranscriptFinalEvent,
    ClearBufferEvent,
    BargeInEvent,
    AudioChunkEvent,
)

__all__ = [
    # Beneficiary
    "Demographics",
    "ProfilingSlots",
    "ConsentAudit",
    "BeneficiaryRecord",
    "BeneficiaryCreate",
    "BeneficiaryUpdate",
    # Course
    "CourseDocument",
    "CourseCreate",
    "CourseSearchQuery",
    "CourseRecommendation",
    # Session
    "SessionState",
    "SessionData",
    "SessionCreate",
    "SessionUpdate",
    "FSMState",
    "SlotStatus",
    "ExtractedSlots",
    # Persistent Call Session
    "CallSessionRecord",
    "TurnRecord",
    "TurnLatencyBreakdown",
    "CallLatencyMetrics",
    # Master LGD & DPIU
    "LgdDistrictRecord",
    "DpiuApplicationRecord",
    # Enterprise Profiling
    "EnterpriseAspirations",
    "ProfileSlots",
    "DialogueState",
    "ConversationalResponse",
    "LLMIntakePayload",
    # WebSocket Events
    "WSMessageType",
    "WSIncomingMessage",
    "WSOutgoingMessage",
    "StartCallEvent",
    "HangupEvent",
    "TranscriptInterimEvent",
    "TranscriptFinalEvent",
    "ClearBufferEvent",
    "BargeInEvent",
    "AudioChunkEvent",
]