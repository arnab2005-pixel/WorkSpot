"""
Pydantic schemas for PM-AJAY Voice Assistant.
"""

from .beneficiary import (
    BeneficiaryCreate,
    BeneficiaryRecord,
    BeneficiaryUpdate,
    ConsentAudit,
    Demographics,
    ProfilingSlots,
)
from .beneficiary_profile import (
    ConversationalResponse,
    DialogueState,
    EnterpriseAspirations,
    LLMIntakePayload,
    ProfileSlots,
)
from .call_session import (
    CallLatencyMetrics,
    CallSessionRecord,
    TurnLatencyBreakdown,
    TurnRecord,
)
from .course import (
    CourseCreate,
    CourseDocument,
    CourseRecommendation,
    CourseSearchQuery,
)
from .dpiu_application import (
    DpiuApplicationRecord,
)
from .lgd_district import (
    LgdDistrictRecord,
)
from .session import (
    ExtractedSlots,
    FSMState,
    SessionCreate,
    SessionData,
    SessionState,
    SessionUpdate,
    SlotStatus,
)
from .websocket_events import (
    AudioChunkEvent,
    BargeInEvent,
    ClearBufferEvent,
    HangupEvent,
    StartCallEvent,
    TranscriptFinalEvent,
    TranscriptInterimEvent,
    WSIncomingMessage,
    WSMessageType,
    WSOutgoingMessage,
)

__all__ = [
    "AudioChunkEvent",
    "BargeInEvent",
    "BeneficiaryCreate",
    "BeneficiaryRecord",
    "BeneficiaryUpdate",
    "CallLatencyMetrics",
    "CallSessionRecord",
    "ClearBufferEvent",
    "ConsentAudit",
    "ConversationalResponse",
    "CourseCreate",
    "CourseDocument",
    "CourseRecommendation",
    "CourseSearchQuery",
    "Demographics",
    "DialogueState",
    "DpiuApplicationRecord",
    "EnterpriseAspirations",
    "ExtractedSlots",
    "FSMState",
    "HangupEvent",
    "LLMIntakePayload",
    "LgdDistrictRecord",
    "ProfileSlots",
    "ProfilingSlots",
    "SessionCreate",
    "SessionData",
    "SessionState",
    "SessionUpdate",
    "SlotStatus",
    "StartCallEvent",
    "TranscriptFinalEvent",
    "TranscriptInterimEvent",
    "TurnLatencyBreakdown",
    "TurnRecord",
    "WSIncomingMessage",
    "WSMessageType",
    "WSOutgoingMessage",
]
