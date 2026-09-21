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

    # 4. Mobility and Intent -> Enterprise Capital probe (or Recommendations)
    res4 = await fsm.step(sess_id, "हम 15 किलोमीटर जा सकते हैं और अपनी दुकान खोलना चाहते हैं")
    if res4["current_state"] == FSMState.ENTERPRISE_CAPITAL.value:
        res5 = await fsm.step(sess_id, "हाँ, सरकारी मदद से नई मशीन चाहिए")
        assert res5["current_state"] in (
            FSMState.RECOMMENDATION_DELIVERY.value,
            FSMState.COMPLETED.value,
        )
        assert len(res5["recommended_courses"]) > 0
        assert res5["recommended_courses"][0]["qp_code"] in ("AMH/Q0301", "EDP/Q0001")
    else:
        assert res4["current_state"] in (
            FSMState.RECOMMENDATION_DELIVERY.value,
            FSMState.COMPLETED.value,
        )
        assert len(res4["recommended_courses"]) > 0
        assert res4["recommended_courses"][0]["qp_code"] in ("AMH/Q0301", "EDP/Q0001")


@pytest.mark.asyncio
async def test_context_chained_progression_concrete_examples():
    """
    Validates concrete examples from PM-AJAY Context-Chained Dialogue Pattern:
    1. Turn N (Location Pindra) -> Turn N+1 (Trade inquiry conditioned on Pindra & ODOP)
    2. Turn N+1 (Trade 2 yrs tailoring) -> Turn N+2 (Intent conditioned on experience: factory vs shop)
    3. Turn N+2 (Intent Own shop) -> Turn N+3 (Capital & machine needs conditioned on shop)
    """
    fsm = ConversationFSM()
    sess_id = "test_chained_progression"
    await fsm.init_session(sess_id)

    # Consent
    await fsm.step(sess_id, "हाँ, हम सहमत हैं")

    # Turn N: User states Location: "हमार घर पिंडरा में बा, वाराणसी।"
    res_loc = await fsm.step(sess_id, "हमार घर पिंडरा में बा, वाराणसी।")
    assert res_loc["current_state"] == FSMState.VOCATIONAL_DISCOVERY.value
    # Assert 3-part conditioned structure: [Empathetic Acknowledgement] + [Entity Hook] + [Target Inquiry]
    assert "पिंडरा तो बाबतपुर के पास है" in res_loc["spoken_response_indic"]
    assert "कालीन, सिलाई और खेती" in res_loc["spoken_response_indic"]
    assert len(res_loc["options"]) >= 3
    assert any("सिलाई" in opt for opt in res_loc["options"])

    # Turn N+1: User states Trade: "हमरे घरे 2 साल से सिलाई के काम होत बा।"
    res_trade = await fsm.step(sess_id, "हमरे घरे 2 साल से सिलाई के काम होत बा।")
    assert res_trade["current_state"] in (FSMState.MOBILITY_AND_INTENT.value, FSMState.ENTERPRISE_CAPITAL.value)
    assert "2 साल का सिलाई का तजुर्बा तो बहुत काम आएगा" in res_trade["spoken_response_indic"]
    assert "गारमेंट फैक्ट्री में पक्की नौकरी" in res_trade["spoken_response_indic"]
    assert "दुकान" in res_trade["spoken_response_indic"]
    assert len(res_trade["options"]) >= 3

    # Turn N+2: User states Intent: "ना, हम दोकान खोलब, आपन काम।"
    res_intent = await fsm.step(sess_id, "ना, हम दोकान खोलब, आपन काम।")
    assert "खुद की दुकान खोलने का फैसला बहुत अच्छा है" in res_intent["spoken_response_indic"]
    assert "मोटर वाली मशीन" in res_intent["spoken_response_indic"]
    assert len(res_intent["options"]) >= 3


@pytest.mark.asyncio
async def test_context_chained_contradiction_repair():
    """
    Validates Contextual Repair when user states WAGE but has 0 km mobility.
    """
    fsm = ConversationFSM()
    sess_id = "test_contradiction"
    await fsm.init_session(sess_id)

    # Consent & Location
    await fsm.step(sess_id, "हाँ")
    await fsm.step(sess_id, "वाराणसी")
    await fsm.step(sess_id, "सिलाई दर्जी")

    # User says factory job but cannot travel (0 km home-bound)
    res_contra = await fsm.step(sess_id, "हम फैक्ट्री में नौकरी करना चाहते हैं लेकिन गाँव से बाहर नहीं जा सकते, घर पर ही")
    assert res_contra["current_state"] == FSMState.CONTEXTUAL_REPAIR.value
    assert "आपने पहले फैक्ट्री में नौकरी की बात कही थी" in res_contra["spoken_response_indic"]
    assert "गाँव से बाहर नहीं जा सकते" in res_contra["spoken_response_indic"]
    assert any("दुकान" in opt for opt in res_contra["options"])
