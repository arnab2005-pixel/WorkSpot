"""
Frontend Development Mock Endpoints for PM-AJAY Voice Assistant.

Exposes:
- POST /api/v1/mock/session/start
- POST /api/v1/mock/interact
Strictly conforms to Section 5.1 of the Project Engineering Specification.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from services.orchestrator.state_machine import ConversationFSM

router = APIRouter(prefix="/api/v1/mock", tags=["mock"])
fsm = ConversationFSM()


class SessionStartResponse(BaseModel):
    session_id: str
    initial_prompt_indic: str
    mock_audio_url: str


class MockInteractRequest(BaseModel):
    session_id: str
    user_transcript: str


class RecommendedCourse(BaseModel):
    qp_code: str
    course_name: str
    training_center: str
    stipend: str


class MockInteractResponse(BaseModel):
    session_id: str
    updated_slots: Dict[str, Any]
    spoken_response_indic: str
    recommended_courses: List[RecommendedCourse]


@router.post("/session/start", response_model=SessionStartResponse)
async def mock_session_start():
    """
    Start a mock session for frontend UI development.
    Conforms to spec section 5.1.
    """
    import uuid
    session_id = f"sess_test_{uuid.uuid4().hex[:5]}"
    await fsm.init_session(session_id)

    return SessionStartResponse(
        session_id=session_id,
        initial_prompt_indic="नमस्ते, मैं पीएम-अजय योजना सहायक हूँ। क्या हम बातचीत शुरू कर सकते हैं?",
        mock_audio_url="/static/audio/mock_greeting.wav",
    )


@router.post("/interact", response_model=MockInteractResponse)
async def mock_interact(req: MockInteractRequest):
    """
    Simulate user transcript turn and receive updated slots and course recommendations.
    Conforms to spec section 5.1.
    """
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    result = await fsm.step(req.session_id, req.user_transcript)

    # Convert recommended courses to model
    courses: List[RecommendedCourse] = []
    for c in result.get("recommended_courses", []):
        courses.append(
            RecommendedCourse(
                qp_code=c.get("qp_code", "AMH/Q0301"),
                course_name=c.get("course_name", "Self Employed Tailor"),
                training_center=c.get("training_center", "Varanasi Skill Center, Cantt"),
                stipend=c.get("stipend", "₹1500 per month"),
            )
        )

    # Ensure fallback course if empty to satisfy frontend mocks
    if not courses and result.get("updated_slots", {}).get("missing_slot") == "COMPLETE":
        courses.append(
            RecommendedCourse(
                qp_code="AMH/Q0301",
                course_name="Self Employed Tailor",
                training_center="Varanasi Skill Center, Cantt",
                stipend="₹1500 per month",
            )
        )

    return MockInteractResponse(
        session_id=req.session_id,
        updated_slots=result.get("updated_slots", {}),
        spoken_response_indic=result.get("spoken_response_indic", "नमस्ते"),
        recommended_courses=courses,
    )
