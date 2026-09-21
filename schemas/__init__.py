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
from .course import (
    CourseCreate,
    CourseDocument,
    CourseRecommendation,
    CourseSearchQuery,
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
    "ClearBufferEvent",
    "ConsentAudit",
    "ConversationalResponse",
    "CourseCreate",
    "CourseDocument",
    "CourseRecommendation",
    "CourseSearchQuery",
    "Demographics",
    "DialogueState",
    "EnterpriseAspirations",
    "ExtractedSlots",
    "FSMState",
    "HangupEvent",
    "LLMIntakePayload",
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
    "WSIncomingMessage",
    "WSMessageType",
    "WSOutgoingMessage",
]
