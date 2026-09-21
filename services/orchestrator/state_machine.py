"""
LangGraph Finite State Machine (FSM) for PM-AJAY Voice Virtual Livelihood Assistant.

Implements the 5 core conversational state nodes:
1. INIT_CONSENT: Explicit voice consent under DPDP Act
2. GEOGRAPHIC_INTAKE: Captures and standardizes district/block
3. VOCATIONAL_DISCOVERY: Identifies traditional or existing trades
4. MOBILITY_AND_INTENT: Resolves commute distance and wage vs self-employment
5. RECOMMENDATION_DELIVERY: Queries vector search and articulates top 2 options
"""

import logging
from datetime import datetime, timezone
from typing import Any

from config.config import get_settings
from schemas.session import (
    ExtractedSlots,
    FSMState,
    ProfilingSlot,
    SessionData,
    SlotStatus,
)
from services.llm.prompt_templates import (
    GREETING_CONSENT_PROMPT,
    LOCATION_PROMPT,
    TRADE_PROMPT,
)
from services.llm.vllm_client import VLLMClient
from services.orchestrator.session_cache import SessionCache
from services.recommendation.embedder import CourseEmbedder
from services.recommendation.mongo_service import MongoService

logger = logging.getLogger(__name__)
settings = get_settings()


class ConversationFSM:
    """
    Orchestrates dialogue state progression across the 5 PM-AJAY intake phases.
    """

    def __init__(
        self,
        session_cache: SessionCache | None = None,
        llm_client: VLLMClient | None = None,
        embedder: CourseEmbedder | None = None,
        mongo_service: MongoService | None = None,
    ):
        self.session_cache = session_cache or SessionCache()
        self.llm_client = llm_client or VLLMClient()
        self.embedder = embedder or CourseEmbedder()
        self.mongo_service = mongo_service or MongoService()

    async def init_session(
        self,
        session_id: str,
        caller_id: str | None = None,
        call_uuid: str | None = None,
    ) -> SessionData:
        """Create and persist a new session at INIT_CONSENT state."""
        phone_hash = None
        if caller_id:
            import hashlib

            phone_hash = hashlib.sha256(caller_id.encode()).hexdigest()

        session = SessionData(
            session_id=session_id,
            call_uuid=call_uuid or f"uuid_{session_id}",
            phone_hash=phone_hash,
            current_state=FSMState.INIT_CONSENT,
            previous_state=FSMState.INIT,
            slots={
                "CONSENT": ProfilingSlot(
                    slot_name="CONSENT", status=SlotStatus.PENDING
                ),
                "LOCATION": ProfilingSlot(
                    slot_name="LOCATION", status=SlotStatus.PENDING
                ),
                "TRADE": ProfilingSlot(slot_name="TRADE", status=SlotStatus.PENDING),
                "MOBILITY": ProfilingSlot(
                    slot_name="MOBILITY", status=SlotStatus.PENDING
                ),
                "INTENT": ProfilingSlot(slot_name="INTENT", status=SlotStatus.PENDING),
            },
        )
        await self.session_cache.save_session(session)
        return session

    async def step(
        self,
        session_id: str,
        user_transcript: str,
    ) -> dict[str, Any]:
        """
        Execute one step of the conversation FSM based on user input.
        """
        session = await self.session_cache.get_session(session_id)
        if not session:
            session = await self.init_session(session_id)

        session.turn_count += 1
        current_state = session.current_state

        # Call LLM to extract slots & generate context
        known = {
            "consent": session.slots.get(
                "CONSENT", ProfilingSlot(slot_name="CONSENT")
            ).value,
            "district_code": session.extracted_entities.get(
                "district_code", "UP_VARANASI"
            ),
            "detected_trade": session.extracted_entities.get("detected_trade"),
            "mobility_radius_km": session.extracted_entities.get(
                "mobility_radius_km", 15
            ),
            "employment_intent": session.extracted_entities.get("employment_intent"),
        }

        extracted: ExtractedSlots = await self.llm_client.extract_slots(
            user_transcript=user_transcript,
            current_state=current_state.value,
            known_slots=known,
        )

        recommended_courses: list[dict[str, Any]] = []
        next_prompt = extracted.spoken_response_indic
        next_state = current_state

        # ==========================================
        # Node 1: INIT_CONSENT
        # ==========================================
        if current_state == FSMState.INIT_CONSENT:
            if extracted.missing_slot != "CONSENT":
                # Voice consent captured
                session.slots["CONSENT"].status = SlotStatus.FILLED
                session.slots["CONSENT"].value = True
                session.slots["CONSENT"].confidence = 0.95
                session.slots["CONSENT"].last_updated = datetime.now(timezone.utc)
                next_state = FSMState.GEOGRAPHIC_INTAKE
                if not next_prompt or "सहमति" in next_prompt:
                    next_prompt = LOCATION_PROMPT
            else:
                next_state = FSMState.INIT_CONSENT
                if not next_prompt:
                    next_prompt = GREETING_CONSENT_PROMPT

        # ==========================================
        # Node 2: GEOGRAPHIC_INTAKE
        # ==========================================
        elif current_state == FSMState.GEOGRAPHIC_INTAKE:
            district = extracted.district_code or "UP_VARANASI"
            session.extracted_entities["district_code"] = district
            session.slots["LOCATION"].status = SlotStatus.FILLED
            session.slots["LOCATION"].value = district
            session.slots["LOCATION"].last_updated = datetime.now(timezone.utc)
            next_state = FSMState.VOCATIONAL_DISCOVERY
            if not next_prompt or "जिले" in next_prompt:
                next_prompt = TRADE_PROMPT

        # ==========================================
        # Node 3: VOCATIONAL_DISCOVERY
        # ==========================================
        elif current_state == FSMState.VOCATIONAL_DISCOVERY:
            trade = extracted.detected_trade or "सिलाई / Tailoring"
            session.extracted_entities["detected_trade"] = trade
            session.slots["TRADE"].status = SlotStatus.FILLED
            session.slots["TRADE"].value = trade
            session.slots["TRADE"].last_updated = datetime.now(timezone.utc)

            # Check if beneficiary explicitly mentions enterprise/shop/business
            is_biz = any(
                w in user_transcript.lower()
                for w in [
                    "दुकान",
                    "खुद का",
                    "मशीन",
                    "स्वरोज़गार",
                    "खोलना",
                    "बिजनेस",
                    "लेईला",
                    "खरीदे",
                ]
            )
            if is_biz:
                next_state = FSMState.ENTERPRISE_SCOPING
                intake = await self.llm_client.extract_enterprise_intake(
                    user_transcript, "ENTERPRISE_SCOPING"
                )
                if intake.profile_slots.enterprise_details:
                    ent_data = intake.profile_slots.enterprise_details
                    session.extracted_entities["enterprise_details"] = (
                        ent_data.model_dump()
                    )
                    if session.phone_hash:
                        await self.mongo_service.process_enterprise_routing(
                            session.phone_hash, ent_data
                        )
                next_prompt = intake.conversational_response.spoken_text_indic
            else:
                next_state = FSMState.MOBILITY_AND_INTENT
                if not next_prompt or "हुनर" in next_prompt:
                    next_prompt = (
                        f"{trade} का काम बहुत मांग में है! "
                        f"आप सीखने के लिए कितनी दूर जा सकते हैं, और खुद की दुकान शुरू करना चाहते हैं या नौकरी?"
                    )

        # ==========================================
        # Node 3.5: ENTERPRISE_SCOPING
        # ==========================================
        elif current_state == FSMState.ENTERPRISE_SCOPING:
            intake = await self.llm_client.extract_enterprise_intake(
                user_transcript, "ENTERPRISE_SCOPING"
            )
            if intake.profile_slots.enterprise_details:
                ent_data = intake.profile_slots.enterprise_details
                session.extracted_entities["enterprise_details"] = ent_data.model_dump()
                session.extracted_entities["employment_intent"] = "SELF_EMPLOYMENT"
                session.slots["INTENT"].status = SlotStatus.FILLED
                session.slots["INTENT"].value = "SELF_EMPLOYMENT"
                if session.phone_hash:
                    await self.mongo_service.process_enterprise_routing(
                        session.phone_hash, ent_data
                    )

            next_state = FSMState.MOBILITY_AND_INTENT
            next_prompt = (
                "प्रशिक्षण और बाज़ार आने-जाने के लिए आप रोज़ कितनी दूर (किलोमीटर) तक जा सकते हैं?"
            )

        # ==========================================
        # Node 4: MOBILITY_AND_INTENT
        # ==========================================
        elif current_state == FSMState.MOBILITY_AND_INTENT:
            intent = extracted.employment_intent or session.extracted_entities.get(
                "employment_intent", "SELF_EMPLOYMENT"
            )
            mobility = extracted.mobility_radius_km or 15

            # If user mentions self-employment here without prior enterprise scoping, extract enterprise goals
            if (
                intent in ("SELF_EMPLOYMENT", "HYBRID")
                and "enterprise_details" not in session.extracted_entities
            ):
                intake = await self.llm_client.extract_enterprise_intake(
                    user_transcript, "ENTERPRISE_SCOPING"
                )
                if intake.profile_slots.enterprise_details:
                    ent_data = intake.profile_slots.enterprise_details
                    session.extracted_entities["enterprise_details"] = (
                        ent_data.model_dump()
                    )
                    if session.phone_hash:
                        await self.mongo_service.process_enterprise_routing(
                            session.phone_hash, ent_data
                        )

            session.extracted_entities["employment_intent"] = intent
            session.extracted_entities["mobility_radius_km"] = mobility
            session.slots["MOBILITY"].status = SlotStatus.FILLED
            session.slots["MOBILITY"].value = mobility
            session.slots["INTENT"].status = SlotStatus.FILLED
            session.slots["INTENT"].value = intent

            next_state = FSMState.RECOMMENDATION_DELIVERY

            # Trigger Vector Search for Node 5 with EDP/RPL routing
            trade_query = session.extracted_entities.get("detected_trade", "सिलाई दर्जी")
            district = session.extracted_entities.get("district_code", "UP_VARANASI")
            query_embedding = self.embedder.embed_text(trade_query)

            is_enterprise = (
                intent in ("SELF_EMPLOYMENT", "HYBRID")
                or "enterprise_details" in session.extracted_entities
            )
            has_exp = (
                float(session.extracted_entities.get("prior_experience_years", 0.0)) > 0
            )

            raw_courses = await self.mongo_service.search_courses(
                query_embedding=query_embedding,
                district_code=district,
                education_tier=1,
                limit=settings.final_recommendation_limit,
                is_enterprise=is_enterprise,
                has_prior_experience=has_exp,
            )

            for c in raw_courses:
                recommended_courses.append(
                    {
                        "qp_code": c.get("qp_code", "AMH/Q0301"),
                        "course_name": c.get("course_name", "Self Employed Tailor"),
                        "training_center": c.get(
                            "training_center", f"{district} Skill Center, Cantt"
                        ),
                        "stipend": c.get("stipend", "₹1500 per month"),
                        "pathway_type": c.get("pathway_type", "VOCATIONAL_TRAINING"),
                    }
                )
            session.recommendations = recommended_courses

            ent_details = session.extracted_entities.get("enterprise_details", {})
            cap_req = ent_details.get("estimated_capital_required_inr")

            if cap_req == "MICRO_UNDER_50K":
                next_prompt = (
                    f"आपके पास के ब्लॉक में {recommended_courses[0]['course_name']} केंद्र है। "
                    f"साथ ही पीएम-अजय योजना के तहत उपकरण व दुकान के लिए ₹50,000 की पूंजीगत सब्सिडी (GIA) हेतु "
                    f"आपका फॉर्म जिला कार्यालय (DPIU) भेजा जा रहा है।"
                )
            elif cap_req == "SMALL_50K_TO_2LAKH":
                next_prompt = (
                    f"आपके पास के ब्लॉक में {recommended_courses[0]['course_name']} केंद्र है। "
                    f"और 2 लाख तक के ऋण हेतु आपका प्रोफ़ाइल NSFDC माइक्रो-क्रेडिट डेस्क को भेजा जा रहा है।"
                )
            else:
                top_name = (
                    recommended_courses[0]["course_name"]
                    if recommended_courses
                    else "प्रशिक्षण"
                )
                next_prompt = f"आपके पास के ब्लॉक में {top_name} और संबंधित कौशल के दो प्रशिक्षण केंद्र हैं। क्या आप दाखिले की जानकारी चाहते हैं?"

        # ==========================================
        # Node 5: RECOMMENDATION_DELIVERY / COMPLETED
        # ==========================================
        elif current_state == FSMState.RECOMMENDATION_DELIVERY:
            next_state = FSMState.COMPLETED
            recommended_courses = session.recommendations
            next_prompt = "आपकी रुचि दर्ज कर ली गई है। प्रशिक्षण केंद्र से आपको जल्द ही संपर्क किया जाएगा। धन्यवाद!"

        # Update session
        session.previous_state = current_state
        session.current_state = next_state
        await self.session_cache.save_session(session)

        # Build response payload
        updated_slots = {
            "detected_trade": session.extracted_entities.get("detected_trade"),
            "mobility_radius_km": session.extracted_entities.get(
                "mobility_radius_km", 15
            ),
            "employment_intent": session.extracted_entities.get("employment_intent"),
            "missing_slot": "COMPLETE"
            if next_state in (FSMState.RECOMMENDATION_DELIVERY, FSMState.COMPLETED)
            else extracted.missing_slot,
        }

        return {
            "session_id": session_id,
            "current_state": next_state.value,
            "updated_slots": updated_slots,
            "spoken_response_indic": next_prompt,
            "recommended_courses": recommended_courses,
        }
