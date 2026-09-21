"""
Session and FSM state models for PM-AJAY Voice Assistant.

These models represent the conversational state machine managed by LangGraph,
backed by Redis for ephemeral session state.
"""

from datetime import datetime
from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class FSMState(str, Enum):
    """Finite State Machine states for the conversation flow."""
    
    INIT = "INIT"
    INIT_CONSENT = "INIT_CONSENT"
    CONSENT_CAPTURED = "CONSENT_CAPTURED"
    GEOGRAPHIC_INTAKE = "GEOGRAPHIC_INTAKE"
    LOCATION_CONFIRMED = "LOCATION_CONFIRMED"
    VOCATIONAL_DISCOVERY = "VOCATIONAL_DISCOVERY"
    EXPERIENCE_DEPTH = "EXPERIENCE_DEPTH"
    ASPIRATIONAL_PROBE = "ASPIRATIONAL_PROBE"
    ENTERPRISE_CAPITAL = "ENTERPRISE_CAPITAL"
    TRAINING_FORMAT = "TRAINING_FORMAT"
    TRADE_IDENTIFIED = "TRADE_IDENTIFIED"
    ENTERPRISE_SCOPING = "ENTERPRISE_SCOPING"
    MOBILITY_AND_INTENT = "MOBILITY_AND_INTENT"
    MOBILITY_CONFIRMED = "MOBILITY_CONFIRMED"
    CONTEXTUAL_REPAIR = "CONTEXTUAL_REPAIR"
    RECOMMENDATION_DELIVERY = "RECOMMENDATION_DELIVERY"
    RECOMMENDATION_DELIVERED = "RECOMMENDATION_DELIVERED"
    ENROLLMENT_INITIATED = "ENROLLMENT_INITIATED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    HANGUP = "HANGUP"


class DialogueTurn(BaseModel):
    """Individual turn record in the context-chained conversation."""
    turn_index: int
    system_question: str
    user_raw_transcript: str
    extracted_slot_key: str
    extracted_slot_value: Any
    confidence: float = 1.0


class DynamicChainedState(BaseModel):
    """
    Context-Chained State Tracking Schema.
    Tracks accumulated profile slots and dialogue trajectory metadata.
    """
    session_id: str
    current_step: str
    # Accumulated Profile
    district: Optional[str] = None
    block: Optional[str] = None
    trade: Optional[str] = None
    prior_experience: Optional[str] = None
    employment_intent: Optional[str] = None  # WAGE vs SELF_EMPLOYMENT
    premise_type: Optional[str] = None
    capital_needed: Optional[str] = None
    mobility_km: Optional[int] = None
    education_level: Optional[str] = None

    # Trajectory & Memory Chaining
    turn_history: List[DialogueTurn] = Field(default_factory=list)
    last_turn_summary: Optional[str] = None
    active_conversational_hook: Optional[str] = None
    options: List[str] = Field(default_factory=list)


class SlotStatus(str, Enum):
    """Status of individual profiling slots."""
    
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    FILLED = "FILLED"
    CONFIRMED = "CONFIRMED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class ProfilingSlot(BaseModel):
    """Individual slot in the beneficiary profiling form."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "slot_name": "CONSENT",
                "status": "FILLED",
                "value": True,
                "confidence": 0.95,
                "attempts": 1,
                "last_updated": "2026-09-20T10:00:00Z"
            }
        }
    )
    
    slot_name: Literal[
        "CONSENT", 
        "LOCATION", 
        "TRADE", 
        "MOBILITY", 
        "INTENT",
        "EDUCATION"
    ]
    status: SlotStatus = SlotStatus.PENDING
    value: Optional[Any] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    attempts: int = Field(default=0, ge=0)
    last_updated: Optional[datetime] = None
    raw_transcript: Optional[str] = None


class SessionData(BaseModel):
    """
    Complete session state stored in Redis.
    
    This is the core state object that flows through the LangGraph FSM.
    """
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "session_id": "sess_abc123def456",
                "call_uuid": "freeswitch-uuid-12345",
                "phone_hash": "a1b2c3d4...",
                "current_state": "VOCATIONAL_DISCOVERY",
                "language": "hi",
                "dialect": "bhojpuri_mixed",
                "slots": {
                    "CONSENT": {"slot_name": "CONSENT", "status": "FILLED", "value": True},
                    "LOCATION": {"slot_name": "LOCATION", "status": "FILLED", "value": "UP_VARANASI"},
                    "TRADE": {"slot_name": "TRADE", "status": "IN_PROGRESS", "value": None},
                    "MOBILITY": {"slot_name": "MOBILITY", "status": "PENDING", "value": None},
                    "INTENT": {"slot_name": "INTENT", "status": "PENDING", "value": None},
                    "EDUCATION": {"slot_name": "EDUCATION", "status": "PENDING", "value": None}
                },
                "extracted_entities": {"detected_trade": "सिलाई"},
                "recommendations": [],
                "audio_vault_refs": ["s3://.../consent.wav"],
                "created_at": "2026-09-20T10:00:00Z",
                "updated_at": "2026-09-20T10:02:30Z"
            }
        }
    )
    
    # Session identifiers
    session_id: str = Field(..., min_length=1, max_length=64)
    call_uuid: Optional[str] = Field(default=None, description="FreeSWITCH call UUID")
    phone_hash: Optional[str] = Field(None, description="Hashed phone for beneficiary lookup")
    
    # Conversation state
    current_state: FSMState = FSMState.INIT
    previous_state: Optional[FSMState] = None
    language: str = "hi"
    dialect: Optional[str] = "bhojpuri_mixed"
    
    # Profiling slots
    slots: Dict[str, ProfilingSlot] = Field(default_factory=dict)
    
    # Context-Chained Dynamic State & Turn History
    chained_state: Optional[DynamicChainedState] = None
    dialogue_turns: List[DialogueTurn] = Field(default_factory=list)

    # Entities extracted by LLM
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    
    # Recommendations generated
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Audio references for audit
    audio_vault_refs: List[str] = Field(default_factory=list)
    
    # Metrics
    turn_count: int = Field(default=0, ge=0)
    total_latency_ms: int = Field(default=0, ge=0)
    asr_latency_ms: int = Field(default=0, ge=0)
    llm_latency_ms: int = Field(default=0, ge=0)
    tts_latency_ms: int = Field(default=0, ge=0)
    vector_search_latency_ms: int = Field(default=0, ge=0)
    
    # Error tracking
    error_count: int = Field(default=0, ge=0)
    last_error: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def get_slot(self, slot_name: str) -> Optional[ProfilingSlot]:
        """Get a slot by name."""
        return self.slots.get(slot_name)
    
    def update_slot(
        self, 
        slot_name: str, 
        value: Any, 
        status: SlotStatus = SlotStatus.FILLED,
        confidence: float = 1.0,
        raw_transcript: Optional[str] = None
    ) -> None:
        """Update a slot value and status."""
        if slot_name not in self.slots:
            self.slots[slot_name] = ProfilingSlot(slot_name=slot_name)
        
        slot = self.slots[slot_name]
        slot.value = value
        slot.status = status
        slot.confidence = confidence
        slot.attempts += 1
        slot.last_updated = datetime.utcnow()
        if raw_transcript:
            slot.raw_transcript = raw_transcript
        
        self.updated_at = datetime.utcnow()
    
    def is_slot_filled(self, slot_name: str) -> bool:
        """Check if a slot is filled or confirmed."""
        slot = self.slots.get(slot_name)
        return slot is not None and slot.status in (SlotStatus.FILLED, SlotStatus.CONFIRMED)
    
    def get_missing_slots(self) -> List[str]:
        """Get list of required slots that are not yet filled."""
        required_slots = ["CONSENT", "LOCATION", "TRADE", "MOBILITY", "INTENT", "EDUCATION"]
        return [
            slot for slot in required_slots 
            if not self.is_slot_filled(slot)
        ]
    
    def all_required_filled(self) -> bool:
        """Check if all required slots are filled."""
        return len(self.get_missing_slots()) == 0


# Alias for compatibility with schemas/__init__.py and consumers
SessionState = SessionData


class SessionCreate(BaseModel):
    """Input for creating a new session."""
    
    call_uuid: str
    phone_hash: Optional[str] = None
    language: str = "hi"
    dialect: Optional[str] = "bhojpuri_mixed"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SessionUpdate(BaseModel):
    """Input for updating session state."""
    
    current_state: Optional[FSMState] = None
    slots: Optional[Dict[str, ProfilingSlot]] = None
    extracted_entities: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    audio_vault_refs: Optional[List[str]] = None
    turn_count: Optional[int] = None
    total_latency_ms: Optional[int] = None
    asr_latency_ms: Optional[int] = None
    llm_latency_ms: Optional[int] = None
    tts_latency_ms: Optional[int] = None
    vector_search_latency_ms: Optional[int] = None
    error_count: Optional[int] = None
    last_error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# State transition rules for validation
VALID_TRANSITIONS: Dict[FSMState, List[FSMState]] = {
    FSMState.INIT: [FSMState.INIT_CONSENT, FSMState.ERROR],
    FSMState.INIT_CONSENT: [FSMState.CONSENT_CAPTURED, FSMState.ERROR, FSMState.HANGUP],
    FSMState.CONSENT_CAPTURED: [FSMState.GEOGRAPHIC_INTAKE, FSMState.ERROR],
    FSMState.GEOGRAPHIC_INTAKE: [FSMState.LOCATION_CONFIRMED, FSMState.ERROR, FSMState.HANGUP],
    FSMState.LOCATION_CONFIRMED: [FSMState.VOCATIONAL_DISCOVERY, FSMState.ERROR],
    FSMState.VOCATIONAL_DISCOVERY: [FSMState.TRADE_IDENTIFIED, FSMState.ERROR, FSMState.HANGUP],
    FSMState.TRADE_IDENTIFIED: [FSMState.MOBILITY_AND_INTENT, FSMState.ERROR],
    FSMState.MOBILITY_AND_INTENT: [FSMState.MOBILITY_CONFIRMED, FSMState.ERROR, FSMState.HANGUP],
    FSMState.MOBILITY_CONFIRMED: [FSMState.RECOMMENDATION_DELIVERY, FSMState.ERROR],
    FSMState.RECOMMENDATION_DELIVERY: [FSMState.RECOMMENDATION_DELIVERED, FSMState.ERROR],
    FSMState.RECOMMENDATION_DELIVERED: [FSMState.ENROLLMENT_INITIATED, FSMState.COMPLETED, FSMState.HANGUP],
    FSMState.ENROLLMENT_INITIATED: [FSMState.COMPLETED, FSMState.ERROR],
    FSMState.COMPLETED: [FSMState.HANGUP],
    FSMState.ERROR: [FSMState.HANGUP],
    FSMState.HANGUP: [],
}


def is_valid_transition(from_state: FSMState, to_state: FSMState) -> bool:
    """Check if a state transition is valid."""
    return to_state in VALID_TRANSITIONS.get(from_state, [])


# Prompts for each FSM state (Hindi/Devanagari)
STATE_PROMPTS: Dict[FSMState, str] = {
    FSMState.INIT_CONSENT: (
        "नमस्ते, मैं पीएम-अजय योजना सहायक हूँ। "
        "यह योजना अनुसूचित जाति के भाई-बहनों के लिए कौशल प्रशिक्षण "
        "और स्वरोज़गार के अवसर प्रदान करती है। "
        "क्या आप अपनी सहमति देते हैं कि हम आपकी जानकारी लेकर "
        "आपके लिए उपयुक्त प्रशिक्षण ढूंढें? कृपया 'हाँ' या 'ना' में जवाब दें।"
    ),
    FSMState.GEOGRAPHIC_INTAKE: (
        "धन्यवाद। कृपया बताएं कि आप किस जिले और ब्लॉक में रहते हैं? "
        "जैसे - वाराणसी जिला, चिरईगांव ब्लॉक।"
    ),
    FSMState.VOCATIONAL_DISCOVERY: (
        "आपके परिवार में या आप खुद क्या काम करते आए हैं? "
        "जैसे - सिलाई, बढ़ई, लोहार, कढ़ाई, राजमिस्त्री, "
        "ब्यूटीशियन, कंप्यूटर, ड्राइविंग, या कोई और हुनर।"
    ),
    FSMState.MOBILITY_AND_INTENT: (
        "आप रोज़ कितनी दूर जा सकते हैं काम या प्रशिक्षण के लिए? "
        "और आप नौकरी करना चाहते हैं या अपना काम शुरू करना चाहते हैं?"
    ),
    FSMState.RECOMMENDATION_DELIVERY: (
        "आपकी जानकारी के आधार पर, आपके पास के दो प्रशिक्षण केंद्र हैं..."
    ),
}


class ExtractedSlots(BaseModel):
    """
    Structured output from LLM for slot extraction.
    
    This matches the Pydantic schema used for constrained JSON decoding
    via Outlines/vLLM.
    """
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detected_trade": "सिलाई / Tailoring",
                "prior_experience_years": 2.0,
                "mobility_radius_km": 15,
                "employment_intent": "SELF_EMPLOYMENT",
                "missing_slot": "COMPLETE",
                "spoken_response_indic": "आपके पास के ब्लॉक में सिलाई और कढ़ाई के दो प्रशिक्षण केंद्र हैं।"
            }
        }
    )
    
    detected_trade: Optional[str] = Field(
        None, 
        description="Identified artisan/vocational skill in Hindi/English"
    )
    prior_experience_years: Optional[float] = Field(default=0.0, ge=0.0)
    mobility_radius_km: Optional[int] = Field(default=15, ge=0, le=100)
    employment_intent: Optional[str] = Field(None, pattern=r"^(WAGE|SELF_EMPLOYMENT|HYBRID)$")
    education_level: Optional[str] = None
    district_code: Optional[str] = None
    block_name: Optional[str] = None
    missing_slot: str = Field(
        ..., 
        description="One of: 'CONSENT', 'LOCATION', 'TRADE', 'MOBILITY', 'INTENT', 'COMPLETE'"
    )
    spoken_response_indic: str = Field(
        ..., 
        description="Empathetic, dialect-friendly next response in Hindi/Devanagari"
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)