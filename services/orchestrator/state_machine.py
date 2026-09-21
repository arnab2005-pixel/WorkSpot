"""
Context-Chained Finite State Machine (FSM) for PM-AJAY Voice Virtual Livelihood Assistant.

Implements the Context-Chained Dialogue Pattern:
Next Turn = [Empathetic Acknowledgement] + [Entity Hook / Bridge] + [Target Inquiry]
with dynamic MCQ question structures, contradiction detection, and slot tracking.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

import httpx
from config.config import get_settings
from schemas.session import (
    SessionData,
    FSMState,
    SlotStatus,
    ProfilingSlot,
    ExtractedSlots,
    DialogueTurn,
    DynamicChainedState,
)
from services.llm.vllm_client import VLLMClient
from services.llm.prompt_templates import (
    GREETING_CONSENT_PROMPT,
    LOCATION_PROMPT,
    TRADE_PROMPT,
    MOBILITY_INTENT_PROMPT,
    FALLBACK_REPROMPT,
)
from services.recommendation.embedder import CourseEmbedder
from services.recommendation.mongo_service import MongoService
from services.orchestrator.session_cache import SessionCache

logger = logging.getLogger(__name__)
settings = get_settings()


# =====================================================================
# Context-Chained Synthesis & Dynamic MCQ Matrix
# =====================================================================

def synthesize_context_chained_turn(
    state: DynamicChainedState,
    target_state: FSMState,
    user_transcript: str,
) -> Tuple[str, List[str]]:
    """
    Synthesizes Turn N+1 dynamically using the three-part conversational structure:
    Next Turn = [Empathetic Acknowledgement] + [Entity Hook / Bridge] + [Target Inquiry]
    and generates contextual MCQ options for rapid touch or voice responses.
    """
    raw_lower = user_transcript.lower().strip()

    # -------------------------------------------------------------
    # 0. Contextual Contradiction Repair
    # -------------------------------------------------------------
    # Scenario: Caller initially states wage/factory intent, but mobility is 0 km (home-bound)
    if (state.employment_intent == "WAGE_EMPLOYMENT" or "फैक्ट्री" in raw_lower or "नौकरी" in raw_lower) and state.mobility_km == 0:
        question = (
            "आपने पहले फैक्ट्री में नौकरी की बात कही थी, लेकिन आप गाँव से बाहर नहीं जा सकते। "
            "क्या आप गाँव के अंदर ही खुद की छोटी सिलाई की दुकान शुरू करना पसंद करेंगे?"
        )
        options = [
            "हाँ, गाँव में ही दुकान खोलेंगे",
            "पास की फैक्ट्री में आ-जा सकेंगे",
            "घर से ही सिलाई का काम करेंगे",
            "सलाहकार से बात करें",
        ]
        return question, options

    # -------------------------------------------------------------
    # 1. INIT_CONSENT -> GEOGRAPHIC_INTAKE
    # -------------------------------------------------------------
    if target_state == FSMState.GEOGRAPHIC_INTAKE:
        question = (
            "बातचीत शुरू करने की सहमति देने के लिए बहुत धन्यवाद! "
            "आपके गाँव और ब्लॉक के अनुसार हम पास के मुफ़्त प्रशिक्षण और रोज़गार के अवसर खोजेंगे— "
            "आप किस जिले और ब्लॉक या गाँव के रहने वाले हैं?"
        )
        options = [
            "वाराणसी, पिंडरा",
            "वाराणसी, चिरईगांव",
            "गाजीपुर",
            "अन्य जिला व ब्लॉक",
        ]
        return question, options

    # -------------------------------------------------------------
    # 2. GEOGRAPHIC_INTAKE -> VOCATIONAL_DISCOVERY
    # -------------------------------------------------------------
    if target_state == FSMState.VOCATIONAL_DISCOVERY:
        loc_str = (state.block or state.district or "").lower()
        if "पिंडरा" in user_transcript or "pindra" in loc_str or "पिंडरा" in loc_str:
            ack = "पिंडरा तो बाबतपुर के पास है, बहुत बढ़िया इलाका है!"
            hook = "वहाँ कालीन, सिलाई और खेती का काम खूब होता है—"
            inquiry = "आप अपने घर में इनमें से कौन सा काम करते हैं, या कुछ नया सीखना चाहते हैं?"
            options = [
                "सिलाई / दर्जी का काम",
                "कालीन बुनाई व हैंडलूम",
                "खेती / किसानी",
                "अन्य नया काम सीखना",
            ]
        elif "चिरईगांव" in user_transcript or "chiraigaon" in loc_str:
            ack = "चिरईगांव तो गंगा किनारे का बहुत उपजाऊ और हुनरमंद क्षेत्र है!"
            hook = "वहाँ कशीदाकारी, सिलाई और कृषि आधारित स्वरोज़गार की बड़ी मांग है—"
            inquiry = "आप अपने घर में कौन सा काम करते हैं, या किस हुनर में मन लगता है?"
            options = [
                "सिलाई और कशीदाकारी",
                "सब्जी व कृषि प्रसंस्करण",
                "बिजली / वायरमैन",
                "अन्य काम",
            ]
        else:
            dist_label = state.district or "वाराणसी"
            ack = f"{dist_label} तो बहुत मेहनती और जागरूक इलाका है!"
            hook = "यहाँ पारंपरिक हस्तशिल्प, सिलाई और आधुनिक तकनीकी कामों के बहुत अवसर हैं—"
            inquiry = "आप अपने घर में इनमें से कौन सा काम करते हैं, या कुछ नया सीखना चाहते हैं?"
            options = [
                "सिलाई / दर्जी",
                "राजमिस्त्री / निर्माण",
                "बिजली / वायरमैन",
                "अन्य नया हुनर",
            ]
        return f"{ack} {hook} {inquiry}", options

    # -------------------------------------------------------------
    # 3. VOCATIONAL_DISCOVERY -> INTENT / EXPERIENCE / CAPITAL
    # -------------------------------------------------------------
    if target_state in (FSMState.MOBILITY_AND_INTENT, FSMState.EXPERIENCE_DEPTH, FSMState.ASPIRATIONAL_PROBE):
        trade = (state.trade or "").lower()
        has_years = "साल" in user_transcript or "वर्ष" in user_transcript or "year" in raw_lower
        is_tailoring = any(w in trade or w in raw_lower for w in ["सिलाई", "दर्जी", "tailor", "कपड़ा", "गारमेंट"])
        is_masonry = any(w in trade or w in raw_lower for w in ["राजमिस्त्री", "मिस्त्री", "mason", "निर्माण", "ईंट", "जोड़ाई"])
        is_unskilled = any(w in trade or w in raw_lower for w in ["मजदूरी", "दैनिक", "unskilled", "कुछ नहीं", "खेतिहर"])

        if is_masonry:
            ack = "राजमिस्त्री का काम बहुत हुनर और मेहनत का काम है!"
            hook = "आजकल आधुनिक निर्माण में टाइल्स और प्लास्टर की मांग बहुत बढ़ गई है—"
            inquiry = "क्या आप सिर्फ ईंट-जोड़ाई करते हैं, या प्लास्टर और टाइल्स का काम भी आता है?"
            options = [
                "ईंट-जोड़ाई और प्लास्टर",
                "टाइल्स और मार्बल फिटिंग",
                "सीखना चाहते हैं",
                "ठेकेदारी / खुद का काम",
            ]
            return f"{ack} {hook} {inquiry}", options

        elif is_unskilled:
            ack = "मेहनत-मजदूरी से परिवार चलाना बहुत सराहनीय है।"
            hook = "कम समय में नया हुनर सीखकर आपकी आमदनी दोगुनी हो सकती है—"
            inquiry = "क्या बिजली का तार जोड़ने (वायरमैन) या मोटरसाइकिल रिपेयरिंग में मन लगता है?"
            options = [
                "बिजली का काम (वायरमैन)",
                "मोटरसाइकिल / ऑटो रिपेयरिंग",
                "सोलर पैनल काम",
                "अन्य हुनर",
            ]
            return f"{ack} {hook} {inquiry}", options

        elif is_tailoring:
            if has_years or state.prior_experience:
                ack = "2 साल का सिलाई का तजुर्बा तो बहुत काम आएगा!"
            else:
                ack = "सिलाई का हुनर तो घर-घर में काम आने वाला शानदार हुनर है!"
            hook = "इस तजुर्बे के साथ आप किसी गारमेंट फैक्ट्री में पक्की नौकरी करना चाहेंगे,"
            inquiry = "या पिंडरा बाज़ार में खुद की सिलाई की दुकान खोलना चाहते हैं?"
            options = [
                "खुद की दुकान खोलना (स्वरोज़गार)",
                "गारमेंट फैक्ट्री में नौकरी",
                "घर से ही सिलाई करना",
                "दोनों चलेगा",
            ]
            return f"{ack} {hook} {inquiry}", options

        else:
            trade_name = state.trade or "इस काम"
            ack = f"{trade_name} का काम स्थानीय बाज़ार में बहुत मांग में है!"
            hook = "इस हुनर के साथ आप किसी इकाई में पक्की नौकरी कर सकते हैं या अपनी दुकान खोल सकते हैं—"
            inquiry = "आप नौकरी करना अधिक पसंद करेंगे, या खुद का छोटा काम शुरू करना?"
            options = [
                "खुद की दुकान / काम",
                "पक्की नौकरी (फैक्ट्री/दफ्तर)",
                "घर से काम करना",
                "दोनों में रुचि है",
            ]
            return f"{ack} {hook} {inquiry}", options

    # -------------------------------------------------------------
    # 4. ENTERPRISE_CAPITAL / ENTERPRISE_SCOPING (Self-employment branch)
    # -------------------------------------------------------------
    if target_state in (FSMState.ENTERPRISE_CAPITAL, FSMState.ENTERPRISE_SCOPING):
        ack = "खुद की दुकान खोलने का फैसला बहुत अच्छा है, आप खुद के मालिक बनेंगे।"
        hook = "सिलाई और शिल्प की दुकान के लिए पीएम-अजय योजना से ₹20,000-₹50,000 की पूंजीगत सब्सिडी (GIA) मिल सकती है—"
        inquiry = "सिलाई की दुकान के लिए क्या आपके पास पहले से मोटर वाली मशीन है, या ₹20,000-₹30,000 की सरकारी मदद से नई मशीन और कैंची-धागा खरीदना चाहेंगे?"
        options = [
            "सरकारी मदद से नई मशीन व धागा",
            "पहले से मोटर वाली मशीन है",
            "स्थान / कमरा किराए पर लेना है",
            "₹50,000 तक की पूंजी चाहिए",
        ]
        return f"{ack} {hook} {inquiry}", options

    # -------------------------------------------------------------
    # 5. MOBILITY -> TRAINING_FORMAT (Home-bound vs Travelling)
    # -------------------------------------------------------------
    if target_state == FSMState.TRAINING_FORMAT:
        if state.mobility_km == 0 or "घर" in raw_lower or "0" in raw_lower:
            ack = "घर की जिम्मेदारियों के साथ काम संभालना बहुत समझदारी का निर्णय है।"
            hook = "गाँव के अंदर ही स्वयं सहायता समूह और पंचायत भवन में मुफ़्त प्रशिक्षण दिया जाता है—"
            inquiry = "घर पर रहकर ही काम करना है, तो क्या आपके गाँव के पंचायत भवन में आकर 15 दिन सीखना ठीक रहेगा?"
            options = [
                "हाँ, पंचायत भवन में ठीक है",
                "स्वयं सहायता समूह (SHG)",
                "गाँव के आंगनवाड़ी केंद्र में",
                "घर पर ही सीखना",
            ]
        else:
            ack = f"{state.mobility_km or 15} किमी तक आने-जाने की तैयारी से आपको जिले के मुख्य कौशल केंद्र में दाखिला मिल सकेगा।"
            hook = "केंद्र पर मुफ्त प्रशिक्षण, ₹1,500/माह वजीफा और मुफ़्त टूल-किट दी जाती है—"
            inquiry = "क्या आप सुबह के 2 घंटे के सत्र में सीखना चाहेंगे या दोपहर के बैच में?"
            options = [
                "सुबह का बैच (9 से 12)",
                "दोपहर का बैच (1 से 4)",
                "सप्ताहांत (शनिवार-रविवार)",
                "पूर्णकालिक (Full-time)",
            ]
        return f"{ack} {hook} {inquiry}", options

    # -------------------------------------------------------------
    # 6. RECOMMENDATION_DELIVERY
    # -------------------------------------------------------------
    if target_state in (FSMState.RECOMMENDATION_DELIVERY, FSMState.COMPLETED):
        question = (
            "बहुत-बहुत धन्यवाद! आपकी रुचि और पते के आधार पर नज़दीकी NSQF प्रशिक्षण और "
            "पीएम-अजय ₹50,000 पूंजीगत सब्सिडी (GIA) के सर्वोत्तम विकल्प तैयार हैं। नीचे दिए गए विकल्पों को देखें:"
        )
        options = [
            "दाखिले के लिए आवेदन करें",
            "दुकान हेतु ₹50,000 सब्सिडी फॉर्म",
            "पास का कौशल केंद्र देखें",
            "सलाहकार से बात करें",
        ]
        return question, options

    # Fallback
    return FALLBACK_REPROMPT, ["हाँ", "नहीं", "दोबारा पूछें", "मदद"]


async def generate_conditioned_question_llm(
    state: DynamicChainedState,
    llm_url: str = "http://127.0.0.1:8000/v1/chat/completions",
    timeout_s: float = 1.5,
) -> Optional[str]:
    """
    Optional dynamic LLM call to Qwen/vLLM injecting prior trajectory context.
    Falls back gracefully if vLLM is offline.
    """
    last_turn = state.turn_history[-1] if state.turn_history else None
    system_prompt = f"""\
You are the PM-AJAY conversational voice intake assistant speaking in natural, rural Hindi.
You are formulating the NEXT question.

CONTEXT OF PREVIOUS TURNS:
- Location: {state.district or 'Not stated'}, Block: {state.block or 'Not stated'}
- Trade: {state.trade or 'Not stated'} (Experience: {state.prior_experience or 'None'})
- Intent: {state.employment_intent or 'Not stated'}
- Last Spoken by Beneficiary: "{last_turn.user_raw_transcript if last_turn else 'Call Started'}"
- Last Extracted Data: {last_turn.extracted_slot_key if last_turn else 'None'} = {last_turn.extracted_slot_value if last_turn else 'None'}

RULES:
1. First sentence MUST acknowledge or praise what the user just said (e.g., mention their trade or location).
2. Second sentence MUST ask the next question, directly referencing what they told you.
3. Maximum 22 words total. Keep it conversational for telephony audio.
"""
    prompt = f"Ask the next question to find out: {state.current_step}"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                llm_url,
                json={
                    "model": "Qwen/Qwen2.5-3B-Instruct",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 80,
                },
                timeout=timeout_s,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    return None


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
        session_cache: Optional[SessionCache] = None,
        llm_client: Optional[VLLMClient] = None,
        embedder: Optional[CourseEmbedder] = None,
        mongo_service: Optional[MongoService] = None,
    ):
        self.session_cache = session_cache or SessionCache()
        self.llm_client = llm_client or VLLMClient()
        self.embedder = embedder or CourseEmbedder()
        self.mongo_service = mongo_service or MongoService()

    async def init_session(
        self,
        session_id: str,
        caller_id: Optional[str] = None,
        call_uuid: Optional[str] = None,
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
                "CONSENT": ProfilingSlot(slot_name="CONSENT", status=SlotStatus.PENDING),
                "LOCATION": ProfilingSlot(slot_name="LOCATION", status=SlotStatus.PENDING),
                "TRADE": ProfilingSlot(slot_name="TRADE", status=SlotStatus.PENDING),
                "MOBILITY": ProfilingSlot(slot_name="MOBILITY", status=SlotStatus.PENDING),
                "INTENT": ProfilingSlot(slot_name="INTENT", status=SlotStatus.PENDING),
            },
        )
        await self.session_cache.save_session(session)
        return session

    async def step(
        self,
        session_id: str,
        user_transcript: str,
    ) -> Dict[str, Any]:
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
            "consent": session.slots.get("CONSENT", ProfilingSlot(slot_name="CONSENT")).value,
            "district_code": session.extracted_entities.get("district_code", chained.district or "UP_VARANASI"),
            "detected_trade": session.extracted_entities.get("detected_trade", chained.trade),
            "mobility_radius_km": session.extracted_entities.get("mobility_radius_km", chained.mobility_km or 15),
            "employment_intent": session.extracted_entities.get("employment_intent", chained.employment_intent),
        }

        extracted: ExtractedSlots = await self.llm_client.extract_slots(
            user_transcript=user_transcript,
            current_state=current_state.value,
            known_slots=known,
        )

        recommended_courses: List[Dict[str, Any]] = []
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
                session.extracted_entities["prior_experience_years"] = float(exp_match.group(1))

            session.extracted_entities["detected_trade"] = trade
            session.slots["TRADE"].status = SlotStatus.FILLED
            session.slots["TRADE"].value = trade
            session.slots["TRADE"].last_updated = datetime.now(timezone.utc)
            chained.trade = trade
            slot_key = "TRADE"
            slot_val = trade

            # Check if user mentions enterprise / shop / business directly
            is_biz = any(w in user_transcript.lower() for w in ["दुकान", "खुद का", "मशीन", "स्वरोज़गार", "खोलना", "बिजनेस", "दोकान"])
            if is_biz:
                next_state = FSMState.ENTERPRISE_CAPITAL
                chained.employment_intent = "SELF_EMPLOYMENT"
                session.extracted_entities["employment_intent"] = "SELF_EMPLOYMENT"
                session.slots["INTENT"].status = SlotStatus.FILLED
                session.slots["INTENT"].value = "SELF_EMPLOYMENT"
                intake = await self.llm_client.extract_enterprise_intake(user_transcript, "ENTERPRISE_SCOPING")
                if intake.profile_slots.enterprise_details:
                    ent_data = intake.profile_slots.enterprise_details
                    session.extracted_entities["enterprise_details"] = ent_data.model_dump()
                    if session.phone_hash:
                        await self.mongo_service.process_enterprise_routing(session.phone_hash, ent_data)
            else:
                next_state = FSMState.MOBILITY_AND_INTENT

        # ==========================================
        # Node 3.5: ENTERPRISE_CAPITAL / ENTERPRISE_SCOPING
        # ==========================================
        elif current_state in (FSMState.ENTERPRISE_CAPITAL, FSMState.ENTERPRISE_SCOPING):
            slot_key = "CAPITAL_AND_PREMISE"
            slot_val = user_transcript
            chained.employment_intent = "SELF_EMPLOYMENT"
            chained.capital_needed = "₹30,000-₹50,000 (GIA Asset Grant)"
            intake = await self.llm_client.extract_enterprise_intake(user_transcript, "ENTERPRISE_SCOPING")
            if intake.profile_slots.enterprise_details:
                ent_data = intake.profile_slots.enterprise_details
                session.extracted_entities["enterprise_details"] = ent_data.model_dump()
                if session.phone_hash:
                    await self.mongo_service.process_enterprise_routing(session.phone_hash, ent_data)

            # Move to mobility/training format or directly to recommendations if mobility is already known
            if session.slots.get("MOBILITY") and session.slots["MOBILITY"].status == SlotStatus.FILLED:
                next_state = FSMState.RECOMMENDATION_DELIVERY
            else:
                next_state = FSMState.TRAINING_FORMAT

        # ==========================================
        # Node 4: MOBILITY_AND_INTENT / TRAINING_FORMAT
        # ==========================================
        elif current_state in (FSMState.MOBILITY_AND_INTENT, FSMState.TRAINING_FORMAT):
            raw_t = user_transcript.lower()
            intent = extracted.employment_intent or session.extracted_entities.get("employment_intent")
            if any(w in raw_t for w in ["दुकान", "दोकान", "खुद का", "स्वरोज़गार", "बिजनेस", "आपन काम"]):
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
            if any(w in raw_t for w in ["घर", "गाँव में ही", "बाहर नहीं", "0 किमी", "0 km"]):
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
            if intent == "SELF_EMPLOYMENT" and "enterprise_details" not in session.extracted_entities:
                intake = await self.llm_client.extract_enterprise_intake(user_transcript, "ENTERPRISE_SCOPING")
                if intake.profile_slots.enterprise_details:
                    ent_data = intake.profile_slots.enterprise_details
                    session.extracted_entities["enterprise_details"] = ent_data.model_dump()
                    if session.phone_hash:
                        await self.mongo_service.process_enterprise_routing(session.phone_hash, ent_data)

            # Check for contradiction: WAGE + 0 km
            if intent == "WAGE_EMPLOYMENT" and mobility == 0 and current_state != FSMState.CONTEXTUAL_REPAIR:
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
            trade_query = session.extracted_entities.get("detected_trade", chained.trade or "सिलाई दर्जी")
            district = session.extracted_entities.get("district_code", chained.district or "UP_VARANASI")
            query_embedding = self.embedder.embed_text(trade_query)

            is_enterprise = chained.employment_intent in ("SELF_EMPLOYMENT", "HYBRID") or "enterprise_details" in session.extracted_entities
            has_exp = float(session.extracted_entities.get("prior_experience_years", 0.0)) > 0

            raw_courses = await self.mongo_service.search_courses(
                query_embedding=query_embedding,
                district_code=district,
                education_tier=1,
                limit=settings.final_recommendation_limit,
                is_enterprise=is_enterprise,
                has_prior_experience=has_exp,
            )

            for c in raw_courses:
                recommended_courses.append({
                    "qp_code": c.get("qp_code", "AMH/Q0301"),
                    "course_name": c.get("course_name", "Self Employed Tailor"),
                    "training_center": c.get("training_center", f"{district} District Skill Center"),
                    "stipend": c.get("stipend", "₹1500 per month"),
                    "pathway_type": c.get("pathway_type", "VOCATIONAL_TRAINING"),
                })
            session.recommendations = recommended_courses

        # ---------------------------------------------------------
        # Synthesize Context-Chained Question and Dynamic MCQ Options
        # ---------------------------------------------------------
        chained.current_step = next_state.value
        spoken_question, dynamic_options = synthesize_context_chained_turn(
            state=chained,
            target_state=next_state,
            user_transcript=user_transcript,
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
            "detected_trade": session.extracted_entities.get("detected_trade", chained.trade),
            "mobility_radius_km": session.extracted_entities.get("mobility_radius_km", chained.mobility_km or 15),
            "employment_intent": session.extracted_entities.get("employment_intent", chained.employment_intent),
            "district": chained.district,
            "block": chained.block,
            "missing_slot": "COMPLETE" if next_state in (FSMState.RECOMMENDATION_DELIVERY, FSMState.COMPLETED) else extracted.missing_slot,
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
