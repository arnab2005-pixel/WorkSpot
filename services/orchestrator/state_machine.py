"""
Context-Chained Finite State Machine (FSM) for PM-AJAY Voice Virtual Livelihood Assistant.

Implements the Context-Chained Dialogue Pattern:
Next Turn = [Empathetic Acknowledgement] + [Entity Hook / Bridge] + [Target Inquiry]
with dynamic MCQ question structures, contradiction detection, and slot tracking.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any

from config.config import get_settings
from schemas.session import (
    DialogueTurn,
    DynamicChainedState,
    ExtractedSlots,
    FSMState,
    ProfilingSlot,
    SessionData,
    SlotStatus,
)
from services.llm.vllm_client import VLLMClient
from services.orchestrator.dialogue_synthesizer import synthesize_context_chained_turn
from services.orchestrator.session_cache import SessionCache
from services.recommendation.embedder import CourseEmbedder
from services.recommendation.mongo_service import MongoService

logger = logging.getLogger(__name__)
settings = get_settings()


# =====================================================================
# Main Conversation FSM
# =====================================================================


class ConversationFSM:
    """
    Orchestrates dialogue state progression across the 5 PM-AJAY intake phases
    with the Context-Chained Dialogue Pattern.
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

        chained = DynamicChainedState(
            session_id=session_id,
            current_step=FSMState.INIT_CONSENT.value,
            options=["हाँ, शुरू करें", "नमस्ते", "योजना की जानकारी"],
        )

        session = SessionData(
            session_id=session_id,
            call_uuid=call_uuid or f"uuid_{session_id}",
            phone_hash=phone_hash,
            current_state=FSMState.INIT_CONSENT,
            previous_state=FSMState.INIT,
            chained_state=chained,
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
        Execute one step of the context-chained conversation FSM based on user input.
        """
        session = await self.session_cache.get_session(session_id)
        if not session:
            session = await self.init_session(session_id)

        session.turn_count += 1
        current_state = session.current_state

        if not session.chained_state:
            session.chained_state = DynamicChainedState(
                session_id=session_id,
                current_step=current_state.value,
            )
        chained = session.chained_state

        # Known slots for extractor
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
        slot_key = ""
        slot_val = None

        # ==========================================
        # Node 1: INIT_CONSENT
        # ==========================================
        if current_state == FSMState.INIT_CONSENT:
            if extracted.missing_slot != "CONSENT":
                session.slots["CONSENT"].status = SlotStatus.FILLED
                session.slots["CONSENT"].value = True
                session.slots["CONSENT"].confidence = 0.95
                session.slots["CONSENT"].last_updated = datetime.now(timezone.utc)
                next_state = FSMState.GEOGRAPHIC_INTAKE
                slot_key = "CONSENT"
                slot_val = True
            else:
                next_state = FSMState.INIT_CONSENT
                slot_key = "CONSENT"
                slot_val = False

        # ==========================================
        # Node 2: GEOGRAPHIC_INTAKE
        # ==========================================
        elif current_state == FSMState.GEOGRAPHIC_INTAKE:
            raw_t = user_transcript
            district = extracted.district_code or "UP_VARANASI"
            block = None
            if "पिंडरा" in raw_t or "pindra" in raw_t.lower():
                block = "पिंडरा (Pindra)"
                district = "UP_VARANASI"
            elif "चिरईगांव" in raw_t or "chiraigaon" in raw_t.lower():
                block = "चिरईगांव (Chiraigaon)"
                district = "UP_VARANASI"

            session.extracted_entities["district_code"] = district
            if block:
                session.extracted_entities["block"] = block
                chained.block = block
            chained.district = district

            session.slots["LOCATION"].status = SlotStatus.FILLED
            session.slots["LOCATION"].value = district
            session.slots["LOCATION"].last_updated = datetime.now(timezone.utc)
            next_state = FSMState.VOCATIONAL_DISCOVERY
            slot_key = "LOCATION"
            slot_val = f"{district} / {block or 'General'}"

        # ==========================================
        # Node 3: VOCATIONAL_DISCOVERY
        # ==========================================
        elif current_state == FSMState.VOCATIONAL_DISCOVERY:
            trade = extracted.detected_trade or "सिलाई / Tailoring"
            # Parse experience if stated
            exp_match = re.search(r"(\d+)\s*(साल|वर्ष|year)", user_transcript)
            exp_str = f"{exp_match.group(1)} वर्ष" if exp_match else None
            if exp_str:
                chained.prior_experience = exp_str
                session.extracted_entities["prior_experience_years"] = float(
                    exp_match.group(1)
                )

            session.extracted_entities["detected_trade"] = trade
            session.slots["TRADE"].status = SlotStatus.FILLED
            session.slots["TRADE"].value = trade
            session.slots["TRADE"].last_updated = datetime.now(timezone.utc)
            chained.trade = trade
            slot_key = "TRADE"
            slot_val = trade

            # Check if user mentions enterprise / shop / business directly
            is_biz = any(
                w in user_transcript.lower()
                for w in [
                    "दुकान",
                    "खुद का",
                    "मशीन",
                    "स्वरोज़गार",
                    "खोलना",
                    "बिजनेस",
                    "दोकान",
                ]
            )
            if is_biz:
                next_state = FSMState.ENTERPRISE_CAPITAL
                chained.employment_intent = "SELF_EMPLOYMENT"
                session.extracted_entities["employment_intent"] = "SELF_EMPLOYMENT"
                session.slots["INTENT"].status = SlotStatus.FILLED
                session.slots["INTENT"].value = "SELF_EMPLOYMENT"
                intake = await self.llm_client.extract_enterprise_intake(
                    user_transcript, "ENTERPRISE_SCOPING"
                )

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
                        await self.mongo_service.process_enterprise_routing(
                            session.phone_hash, ent_data
                        )
                next_prompt = intake.conversational_response.spoken_text_indic
            else:
                next_state = FSMState.MOBILITY_AND_INTENT

        # ==========================================
        # Node 3.5: ENTERPRISE_CAPITAL / ENTERPRISE_SCOPING
        # ==========================================
        elif current_state in (
            FSMState.ENTERPRISE_CAPITAL,
            FSMState.ENTERPRISE_SCOPING,
        ):
            slot_key = "CAPITAL_AND_PREMISE"
            slot_val = user_transcript
            chained.employment_intent = "SELF_EMPLOYMENT"
            chained.capital_needed = "₹30,000-₹50,000 (GIA Asset Grant)"
            intake = await self.llm_client.extract_enterprise_intake(
                user_transcript, "ENTERPRISE_SCOPING"
            )
        elif current_state == FSMState.ENTERPRISE_SCOPING:
            intake = await self.llm_client.extract_enterprise_intake(
                user_transcript, "ENTERPRISE_SCOPING"
            )
            if intake.profile_slots.enterprise_details:
                ent_data = intake.profile_slots.enterprise_details
                session.extracted_entities["enterprise_details"] = ent_data.model_dump()
                if session.phone_hash:
                    await self.mongo_service.process_enterprise_routing(
                        session.phone_hash, ent_data
                    )

            # Move to mobility/training format or directly to recommendations if mobility is already known
            if (
                session.slots.get("MOBILITY")
                and session.slots["MOBILITY"].status == SlotStatus.FILLED
            ):
                next_state = FSMState.RECOMMENDATION_DELIVERY
            else:
                next_state = FSMState.TRAINING_FORMAT
            next_state = FSMState.MOBILITY_AND_INTENT
            next_prompt = (
                "प्रशिक्षण और बाज़ार आने-जाने के लिए आप रोज़ कितनी दूर (किलोमीटर) तक जा सकते हैं?"
            )

        # ==========================================
        # Node 4: MOBILITY_AND_INTENT / TRAINING_FORMAT
        # ==========================================
        elif current_state in (FSMState.MOBILITY_AND_INTENT, FSMState.TRAINING_FORMAT):
            raw_t = user_transcript.lower()
            intent = extracted.employment_intent or session.extracted_entities.get(
                "employment_intent"
            )
            if any(
                w in raw_t
                for w in ["दुकान", "दोकान", "खुद का", "स्वरोज़गार", "बिजनेस", "आपन काम"]
            ):
                intent = "SELF_EMPLOYMENT"
            elif any(w in raw_t for w in ["फैक्ट्री", "नौकरी", "मजदूरी"]):
                intent = "WAGE_EMPLOYMENT"
            elif not intent:
                intent = "SELF_EMPLOYMENT"

            chained.employment_intent = intent
            session.extracted_entities["employment_intent"] = intent
            session.slots["INTENT"].status = SlotStatus.FILLED
            session.slots["INTENT"].value = intent

            # Mobility radius
            mobility = extracted.mobility_radius_km
            if any(
                w in raw_t for w in ["घर", "गाँव में ही", "बाहर नहीं", "0 किमी", "0 km"]
            ):
                mobility = 0
            elif mobility is None:
                km_m = re.search(r"(\d+)\s*(किमी|km|किलोमीटर)", raw_t)
                mobility = int(km_m.group(1)) if km_m else 15

            chained.mobility_km = mobility
            session.extracted_entities["mobility_radius_km"] = mobility
            session.slots["MOBILITY"].status = SlotStatus.FILLED
            session.slots["MOBILITY"].value = mobility

            slot_key = "MOBILITY_AND_INTENT"
            slot_val = f"{intent} ({mobility}km)"

            # If user mentions self-employment, extract enterprise details for GIA routing
            if (
                intent == "SELF_EMPLOYMENT"
                and "enterprise_details" not in session.extracted_entities
            ):
                intake = await self.llm_client.extract_enterprise_intake(
                    user_transcript, "ENTERPRISE_SCOPING"
                )
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

            # Check for contradiction: WAGE + 0 km
            if (
                intent == "WAGE_EMPLOYMENT"
                and mobility == 0
                and current_state != FSMState.CONTEXTUAL_REPAIR
            ):
                next_state = FSMState.CONTEXTUAL_REPAIR
            elif intent == "SELF_EMPLOYMENT" and not chained.capital_needed:
                next_state = FSMState.ENTERPRISE_CAPITAL
            else:
                next_state = FSMState.RECOMMENDATION_DELIVERY

        # ==========================================
        # Node 4.5: CONTEXTUAL_REPAIR
        # ==========================================
        elif current_state == FSMState.CONTEXTUAL_REPAIR:
            slot_key = "REPAIR_INTENT"
            if any(w in user_transcript.lower() for w in ["दुकान", "हाँ", "घर से", "गाँव"]):
                chained.employment_intent = "SELF_EMPLOYMENT"
                session.extracted_entities["employment_intent"] = "SELF_EMPLOYMENT"
                session.slots["INTENT"].value = "SELF_EMPLOYMENT"
                slot_val = "Resolved: SELF_EMPLOYMENT"
            else:
                slot_val = "Resolved: Travel allowed"
                chained.mobility_km = 12
                session.extracted_entities["mobility_radius_km"] = 12
            next_state = FSMState.RECOMMENDATION_DELIVERY

        # ==========================================
        # Node 5: RECOMMENDATION_DELIVERY
        # ==========================================
        elif current_state == FSMState.RECOMMENDATION_DELIVERY:
            next_state = FSMState.COMPLETED
            slot_key = "COMPLETION"
            slot_val = "Enrolled"

        # If reaching recommendation delivery, perform course vector search
        if next_state in (FSMState.RECOMMENDATION_DELIVERY, FSMState.COMPLETED):
            trade_query = session.extracted_entities.get(
                "detected_trade", chained.trade or "सिलाई दर्जी"
            )
            district = session.extracted_entities.get(
                "district_code", chained.district or "UP_VARANASI"
            )
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

        spoken_question = next_prompt
        _, dynamic_options = synthesize_context_chained_turn(
            chained, next_state, user_transcript
        )
        chained.active_conversational_hook = spoken_question
        chained.options = dynamic_options

        # Record DialogueTurn in history
        turn_record = DialogueTurn(
            turn_index=session.turn_count,
            system_question=spoken_question,
            user_raw_transcript=user_transcript,
            extracted_slot_key=slot_key,
            extracted_slot_value=slot_val,
            confidence=0.95,
        )
        chained.turn_history.append(turn_record)
        chained.last_turn_summary = f"Turn {session.turn_count}: {slot_key}={slot_val}"
        session.dialogue_turns.append(turn_record)

        # Update and persist session
        session.previous_state = current_state
        session.current_state = next_state
        session.chained_state = chained
        await self.session_cache.save_session(session)

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
            "spoken_response_indic": spoken_question,
            "options": dynamic_options,
            "active_conversational_hook": spoken_question,
            "recommended_courses": recommended_courses,
            "chained_state": chained.model_dump(),
        }
