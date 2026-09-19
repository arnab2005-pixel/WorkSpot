"""
Unit tests for the LangGraph Finite State Machine (FSM).
Tests progression across:
INIT_CONSENT -> GEOGRAPHIC_INTAKE -> VOCATIONAL_DISCOVERY -> MOBILITY_AND_INTENT -> RECOMMENDATION_DELIVERY
"""

import pytest
import pytest_asyncio
from services.orchestrator.state_machine import ConversationFSM
from schemas.session import FSMState, SlotStatus


@pytest.mark.asyncio
async def test_fsm_session_initialization():
    """Verify session starts in INIT_CONSENT state."""
    fsm = ConversationFSM()
    session = await fsm.init_session("test_sess_001", caller_id="9876543210")

    assert session.session_id == "test_sess_001"
    assert session.current_state == FSMState.INIT_CONSENT
    assert "CONSENT" in session.slots
    assert session.slots["CONSENT"].status == SlotStatus.PENDING


@pytest.mark.asyncio
async def test_fsm_consent_turn():
    """Verify voice consent transitions state to GEOGRAPHIC_INTAKE."""
    fsm = ConversationFSM()
    await fsm.init_session("test_sess_002")

    res = await fsm.step("test_sess_002", "हाँ, हम बात करना चाहते हैं")
    assert res["current_state"] == FSMState.GEOGRAPHIC_INTAKE.value
    assert res["updated_slots"]["missing_slot"] in ("LOCATION", "TRADE")


@pytest.mark.asyncio
async def test_fsm_full_flow():
    """Verify end-to-end conversation flow through all 5 nodes."""
    fsm = ConversationFSM()
    sess_id = "test_sess_full"
    await fsm.init_session(sess_id)

    # 1. Consent
    res1 = await fsm.step(sess_id, "हाँ, शुरू करें")
    assert res1["current_state"] == FSMState.GEOGRAPHIC_INTAKE.value

    # 2. Location
    res2 = await fsm.step(sess_id, "हम वाराणसी जिले के चिरईगांव से हैं")
    assert res2["current_state"] == FSMState.VOCATIONAL_DISCOVERY.value

    # 3. Vocational trade
    res3 = await fsm.step(sess_id, "हम सिलाई और दर्जी का काम सीखना चाहते हैं")
    assert res3["current_state"] == FSMState.MOBILITY_AND_INTENT.value
    assert res3["updated_slots"]["detected_trade"] is not None

    # 4. Mobility and Intent -> Recommendations delivered
    res4 = await fsm.step(sess_id, "हम 15 किलोमीटर जा सकते हैं और अपनी दुकान खोलना चाहते हैं")
    assert res4["current_state"] in (
        FSMState.RECOMMENDATION_DELIVERY.value,
        FSMState.COMPLETED.value,
    )
    assert len(res4["recommended_courses"]) > 0
    assert res4["recommended_courses"][0]["qp_code"] == "AMH/Q0301"
