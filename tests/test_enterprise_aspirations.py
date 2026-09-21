"""
Unit tests for Enterprise Aspirations, GIA capital subsidy routing, and dialect parsing.
Verifies PM-AJAY GIA subsidy (up to 50k), NSFDC micro-credit, and EDP/RPL course matching.
"""

import pytest

from schemas.beneficiary_profile import (
    ConversationalResponse,
    DialogueState,
    EnterpriseAspirations,
    LLMIntakePayload,
    ProfileSlots,
)
from services.llm.vllm_client import VLLMClient
from services.recommendation.mongo_service import MongoService


def test_enterprise_aspirations_schema():
    """Verify EnterpriseAspirations and LLMIntakePayload validation."""
    aspirations = EnterpriseAspirations(
        is_interested_in_business=True,
        business_type="REPAIR_SERVICE",
        enterprise_model="INDIVIDUAL",
        estimated_capital_required_inr="MICRO_UNDER_50K",
        own_investment_capacity_inr=5000,
        premise_status="ROADSIDE_STALL",
        machinery_equipment_needed=["shoe_sewing_machine"],
        shg_membership=False,
        target_market="WEEKLY_HAAT",
        scheme_alignment_tag="PM_AJAY_CAPITAL_SUBSIDY",
    )

    payload = LLMIntakePayload(
        profile_slots=ProfileSlots(
            detected_trade="चर्मकार / जूता निर्माण एवं मरम्मत (Leather Craft)",
            standardized_sector="Leather & Leather Goods",
            prior_experience_years=3.0,
            education_level=None,
            mobility_radius_km=5,
            employment_intent="SELF_EMPLOYMENT",
            enterprise_details=aspirations,
        ),
        dialogue_state=DialogueState(
            current_step="ENTERPRISE_SCOPING",
            missing_slots=["EDUCATION", "PREMISE_CONFIRMATION"],
            is_profile_complete=False,
            requires_human_escalation=False,
        ),
        conversational_response=ConversationalResponse(
            spoken_text_indic="दुकान खोलने का विचार बहुत बढ़िया है।",
            target_action="PROBE_PREMISE",
        ),
    )

    assert payload.profile_slots.enterprise_details.is_interested_in_business is True
    assert (
        payload.profile_slots.enterprise_details.estimated_capital_required_inr
        == "MICRO_UNDER_50K"
    )
    assert payload.profile_slots.standardized_sector == "Leather & Leather Goods"


@pytest.mark.asyncio
async def test_bhojpuri_dialect_enterprise_parsing():
    """
    Verify dialect parsing on rural Bhojpuri / Hindi mix beneficiary utterance:
    'हमार बाबूजी चमड़ा के काम करत रहलन, हमहू थोड़ा-बहुत जूता सी लेईला। शहर मजदूरी करे ना जाइब,
    गांव के बजारिए में आपन छोट दुकान खोले के बा। बस मशीन खरीदे खातिर 25-30 हजार रुपया के मदद मिल जात त ठीक रहित।'
    """
    client = VLLMClient()
    utterance = (
        "हमार बाबूजी चमड़ा के काम करत रहलन, हमहू थोड़ा-बहुत जूता सी लेईला। "
        "शहर मजदूरी करे ना जाइब, गांव के बजारिए में आपन छोट दुकान खोले के बा। "
        "बस मशीन खरीदे खातिर 25-30 हजार रुपया के मदद मिल जात त ठीक रहित।"
    )

    intake = client._fallback_extract_enterprise(utterance, "ENTERPRISE_SCOPING")

    assert "Leather" in intake.profile_slots.standardized_sector
    assert intake.profile_slots.employment_intent == "SELF_EMPLOYMENT"

    ent = intake.profile_slots.enterprise_details
    assert ent is not None
    assert ent.is_interested_in_business is True
    assert ent.estimated_capital_required_inr == "MICRO_UNDER_50K"
    assert ent.scheme_alignment_tag == "PM_AJAY_CAPITAL_SUBSIDY"
    assert ent.target_market == "WEEKLY_HAAT"
    assert "shoe_sewing_machine" in ent.machinery_equipment_needed

    assert intake.conversational_response.target_action == "PROBE_PREMISE"
    assert "50,000" in intake.conversational_response.spoken_text_indic


@pytest.mark.asyncio
async def test_capital_subsidy_gia_routing():
    """Verify GIA capital subsidy prefill flagging under 50k and NSFDC routing over 50k."""
    mongo = MongoService()

    # Case 1: Micro capital <= 50k -> PM-AJAY GIA Asset Grant (up to 50k)
    micro_ent = EnterpriseAspirations(
        is_interested_in_business=True,
        estimated_capital_required_inr="MICRO_UNDER_50K",
    )
    routing_micro = await mongo.process_enterprise_routing("hash_123", micro_ent)
    assert routing_micro["eligible_for_gia_asset_grant"] is True
    assert routing_micro["credit_desk_routing"] == "PM_AJAY_CAPITAL_SUBSIDY"
    assert routing_micro["dpiu_prefill_status"] == "PREFILL_DISPATCHED_TO_DPIU"

    # Case 2: Small capital 50k to 2 lakh -> NSFDC Micro-Credit Desk
    small_ent = EnterpriseAspirations(
        is_interested_in_business=True,
        estimated_capital_required_inr="SMALL_50K_TO_2LAKH",
    )
    routing_small = await mongo.process_enterprise_routing("hash_456", small_ent)
    assert routing_small["eligible_for_gia_asset_grant"] is False
    assert routing_small["credit_desk_routing"] == "NSFDC_MICRO_CREDIT"
    assert routing_small["dpiu_prefill_status"] == "ROUTED_TO_NSFDC_DESK"


@pytest.mark.asyncio
async def test_edp_rpl_course_routing():
    """Verify enterprise candidates get routed to EDP/RPL modules instead of entry wage factory courses."""
    mongo = MongoService()
    dummy_vec = [0.05] * 768

    # Candidate with enterprise intent & prior experience -> RPL certification
    rpl_courses = await mongo.search_courses(
        query_embedding=dummy_vec,
        district_code="UP_VARANASI",
        is_enterprise=True,
        has_prior_experience=True,
    )
    assert len(rpl_courses) >= 1
    assert "RPL" in rpl_courses[0]["qp_code"] or "RPL" in rpl_courses[0]["course_name"]

    # Candidate with enterprise intent & no prior experience -> EDP training
    edp_courses = await mongo.search_courses(
        query_embedding=dummy_vec,
        district_code="UP_VARANASI",
        is_enterprise=True,
        has_prior_experience=False,
    )
    assert len(edp_courses) >= 1
    assert "EDP" in edp_courses[0]["qp_code"] or "EDP" in edp_courses[0]["course_name"]
