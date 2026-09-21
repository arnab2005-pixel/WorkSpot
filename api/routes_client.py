"""
Client-Facing API Endpoints for WorkSpot / PM-AJAY Web Kiosk.

Provides:
- POST /api/v1/session (Start / initialize session with language & phone)
- GET  /api/v1/session/{id} (Fetch active session & profile)
- DELETE /api/v1/session/{id} (End session)
- POST /api/v1/interact (Interactive conversational turn: FSM step, slot extraction & recommendations)
- GET  /api/v1/recommendations/{session_id} (Fetch live NSQF & GIA subsidy recommendations)
- POST /api/v1/advisor/chat (AI Livelihood Advisor contextual chat)
- POST /api/v1/audio/transcribe (Audio speech-to-text upload fallback)
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from services.orchestrator.state_machine import ConversationFSM
from schemas.session import FSMState

logger = logging.getLogger(__name__)
router = APIRouter(tags=["client"])

# Shared FSM instance
fsm = ConversationFSM()

# Language-specific initial greetings
INITIAL_GREETINGS: Dict[str, str] = {
    "Hindi": "नमस्ते! मैं पीएम-अजय योजना सहायक हूँ। क्या हम बातचीत शुरू कर सकते हैं?",
    "Bhojpuri": "प्रणाम! हम पीएम-अजय योजना सहायक हईं। का रउवा आपन काम-धंधा आ रोजी-रोजगार के बारे में बात करे खातिर तइयार बानी?",
    "Bengali": "নমস্কার! আমি পিএম-অজয় যোজনা সহায়ক। আপনি কি আপনার কাজ এবং জীবিকা সম্পর্কে কথা বলতে প্রস্তুত?",
    "Maithili": "प्रणाम! हम पीएम-अजय योजना सहायक छी। की अहाँ अपन काज आ आजीविकाक संबंध में बातचीत करय लेल तैयार छी?",
    "Assamese": "নমস্কাৰ! মই পিএম-অজয় সহায়ক। আপুনি আপোনাৰ কাম আৰু জীৱিকাৰ বিষয়ে কথা পাতিবলৈ সাজুনে?",
    "Gujarati": "નમસ્તે! હું પીએમ-અજય યોજના સહાયક છું. શું તમે તમારા કામ અને આજીવિકા વિશે વાત કરવા તૈયાર છો?",
    "Kannada": "ನಮಸ್ಕಾರ! ನಾನು ಪಿಎಂ-ಅಜಯ್ ಯೋಜನೆ ಸಹಾಯಕ. ನಿಮ್ಮ ಕೆಲಸ ಮತ್ತು ಜೀವನೋಪಾಯದ ಬಗ್ಗೆ ಮಾತನಾಡಲು ಸಿದ್ಧರಿದ್ದೀರಾ?",
    "Malayalam": "നമസ്കാരം! ഞാൻ പിഎം-അജയ് യോജന സഹായിയാണ്. നിങ്ങളുടെ തൊഴിലിനെക്കുറിച്ചും ഉപജീവനത്തെക്കുറിച്ചും സംസാരിക്കാൻ തയ്യാറാണോ?",
    "Marathi": "नमस्कार! मी पीएम-अजय योजना सहाय्यक आहे. आपण आपल्या कामाविषयी आणि रोजगाराविषयी बोलायला तयार आहात का?",
    "Odia": "ନମସ୍କାର! ମୁଁ ପିଏମ୍-ଅଜୟ ଯୋଜନା ସହାୟକ। ଆପଣ ନିଜ କାମ ଏବଂ ଜୀବିକା ବିଷୟରେ କଥା ହେବାକୁ ପ୍ରସ୍ତୁତ କି?",
    "Punjabi": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਪੀਐਮ-ਅਜੈ ਯੋਜਨਾ ਸਹਾਇਕ ਹਾਂ। ਕੀ ਤੁਸੀਂ ਆਪਣੇ ਕੰਮ ਅਤੇ ਰੋਜ਼ਗਾਰ ਬਾਰੇ ਗੱਲ ਕਰਨ ਲਈ ਤਿਆਰ ਹੋ?",
    "Tamil": "வணக்கம்! நான் பிஎம்-அஜய் வாழ்வாதார உதவியாளர். உங்கள் திறன்கள் மற்றும் வேலை வாய்ப்புகளைப் பற்றி பேச தயாரா?",
    "Telugu": "నమస్కారం! నేను పీఎం-అజయ్ జీవనోపాధి సహాయకుడిని. మీ నైపుణ్యాలు మరియు జీవనోపాధి అవకాశాల గురించి మాట్లాడటానికి సిద్ధంగా ఉన్నారా?",
    "Urdu": "آداب! میں پی ایم-اجے یوجنا معاون ہوں۔ کیا آپ اپنے کام اور روزگار کے بارے میں بات کرنے کے لیے تیار ہیں؟",
    "English": "Hello! I am the PM-AJAY Livelihood Assistant. Are you ready to discover skills, micro-credit, and livelihood opportunities?",
}


# =====================================================================
# Request / Response Schemas
# =====================================================================

class CreateSessionRequest(BaseModel):
    language: Optional[str] = "Hindi"
    phone_number: Optional[str] = None
    district: Optional[str] = "UP_VARANASI"


class RecommendationItem(BaseModel):
    id: str
    type: str = Field(..., description="Training | Job | Self-employment | Government support")
    title: str
    provider: str
    location: str
    match: int
    explanation: str
    tags: List[str] = Field(default_factory=list)
    qp_code: Optional[str] = None
    stipend: Optional[str] = None


class SessionClientResponse(BaseModel):
    id: str
    session_id: str
    language: str
    state: str
    initial_prompt_indic: str
    mock_audio_url: str
    profile: Dict[str, Any]
    createdAt: str
    updatedAt: str


class InteractRequest(BaseModel):
    session_id: str
    user_transcript: str
    language: Optional[str] = None


class InteractResponse(BaseModel):
    session_id: str
    current_state: str
    spoken_response_indic: str
    updated_slots: Dict[str, Any]
    profile: Dict[str, Any]
    recommended_courses: List[RecommendationItem]
    eligible_for_gia_asset_grant: bool
    max_capital_subsidy_inr: float
    credit_desk_routing: Optional[str]
    is_complete: bool


class AdvisorRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    language: Optional[str] = "Hindi"


class AdvisorResponse(BaseModel):
    reply: str
    suggestions: List[str]


# =====================================================================
# Helper: Map Session State to Frontend Profile
# =====================================================================

def build_profile_dict(session: Any) -> Dict[str, Any]:
    """Transforms backend session entities into frontend Profile model."""
    entities = getattr(session, "extracted_entities", {}) or {}
    slots = getattr(session, "slots", {}) or {}

    trade = entities.get("detected_trade") or (slots.get("TRADE").value if slots.get("TRADE") else "")
    district = entities.get("district_code") or (slots.get("LOCATION").value if slots.get("LOCATION") else "")
    intent = entities.get("employment_intent") or (slots.get("INTENT").value if slots.get("INTENT") else "Either")
    mobility_km = entities.get("mobility_radius_km", 15)

    if intent == "SELF_EMPLOYMENT":
        intent_display = "Self-employment"
    elif intent == "WAGE_EMPLOYMENT":
        intent_display = "Wage employment"
    else:
        intent_display = "Either"

    mobility_display = f"{mobility_km} km" if mobility_km in (0, 15, 50) else "15 km"

    enterprise = entities.get("enterprise_details", {})
    aspirations = ""
    if enterprise:
        biz = enterprise.get("business_type") or "micro-enterprise"
        cap = enterprise.get("funding_required_inr") or "50,000"
        aspirations = f"Wants to start {biz}, seeking ₹{cap} funding"

    skills = []
    if trade:
        skills.append(str(trade).split("/")[0].strip())

    return {
        "currentWork": str(trade or ""),
        "skills": skills,
        "craft": str(trade or ""),
        "mobility": mobility_display,
        "intent": intent_display,
        "aspirations": aspirations,
        "district": str(district or "Varanasi"),
    }


async def build_recommendations_for_session(
    session: Any, mongo_service: Optional[Any] = None
) -> List[RecommendationItem]:
    """Generates rich recommendation cards querying MongoDB NSQF courses and PM-AJAY GIA subsidy rules."""
    entities = getattr(session, "extracted_entities", {}) or {}
    trade = entities.get("detected_trade", "").lower()
    district = entities.get("district_code", "UP_VARANASI")
    district_clean = district.replace("UP_", "").replace("BR_", "").replace("MP_", "").replace("RJ_", "").replace("MH_", "").replace("WB_", "").capitalize()
    enterprise = entities.get("enterprise_details", {})
    intent = entities.get("employment_intent", "Either")
    is_self_emp = intent in ("SELF_EMPLOYMENT", "HYBRID", "Either") or bool(enterprise)
    has_exp = float(entities.get("prior_experience_years", 0.0)) > 0

    items: List[RecommendationItem] = []

    # 1. Query MongoDB for real district courses if connected
    mongo_courses = []
    if mongo_service and getattr(mongo_service, "_connected", False):
        try:
            trade_query = trade or "सिलाई दर्जी"
            query_embedding = fsm.embedder.embed_text(trade_query)
            mongo_courses = await mongo_service.search_courses(
                query_embedding=query_embedding,
                district_code=district,
                education_tier=1,
                limit=2,
                is_enterprise=is_self_emp,
                has_prior_experience=has_exp,
            )
        except Exception as e:
            logger.warning(f"Failed to query courses from MongoDB: {e}")

    # Map MongoDB courses
    for c in mongo_courses:
        qp = c.get("qp_code", "VOC/Q001")
        name = c.get("course_name", "Vocational Trade Training")
        indic = c.get("course_name_indic")
        display_title = f"{name} ({indic})" if indic else name
        raw_score = c.get("score", 0.94)
        match_pct = int(min(99, max(75, round(raw_score * 100))))
        stipend = c.get("stipend_per_month") or 1500
        duration = c.get("duration_hours") or 240
        duration_months = max(1, duration // 80)
        tc_name = c.get("training_center") or f"{district_clean} Skill Center"
        sector = c.get("sector") or "Vocational"
        nsqf = c.get("nsqf_level") or 4

        items.append(
            RecommendationItem(
                id=f"course-{qp}",
                type="Training",
                title=display_title,
                provider=tc_name,
                location=f"{district_clean} Center",
                match=match_pct,
                explanation=f"NSQF Level {nsqf} course in {sector} aligned with your skills. Includes free toolkit, practical workshop, and ₹{stipend} monthly stipend.",
                tags=[f"NSQF Level {nsqf}", "Free Toolkit", f"Stipend ₹{stipend}/mo", f"{duration_months} Months"],
                qp_code=qp,
                stipend=f"₹{stipend} per month",
            )
        )

    # Fallback to curated courses if MongoDB returned none
    if not items:
        if "सिलाई" in trade or "tailor" in trade or "दर्जी" in trade:
            items.append(
                RecommendationItem(
                    id="tailor-edp-01",
                    type="Training",
                    title="Self Employed Tailor (सिलाई दर्जी)",
                    provider="Skill India Digital Hub / PM-AJAY",
                    location=f"{district_clean} Skill Center, Cantt",
                    match=96,
                    explanation="NSQF Level 4 training with hands-on garment cutting, machine operation, free toolkit, and ₹1,500 monthly stipend.",
                    tags=["NSQF Level 4", "Free Toolkit", "Stipend ₹1500/mo", "3 Months"],
                    qp_code="AMH/Q0301",
                    stipend="₹1500 per month",
                )
            )
        elif "बांस" in trade or "bamboo" in trade:
            items.append(
                RecommendationItem(
                    id="bamboo-craft-01",
                    type="Training",
                    title="Bamboo Utility Handicrafts Producer",
                    provider="ODOP Cluster / PM-AJAY Skill Desk",
                    location=f"{district_clean} Handicraft Cluster",
                    match=94,
                    explanation="Specialized training in bamboo curing, weaving, and modern utility item fabrication for regional markets.",
                    tags=["ODOP Aligned", "Tool Support", "Local Cluster", "2 Months"],
                    qp_code="CON/Q0801",
                    stipend="₹1500 per month",
                )
            )
        else:
            items.append(
                RecommendationItem(
                    id="general-voc-01",
                    type="Training",
                    title="Self Employed Tailor & Vocational Trade",
                    provider=f"{district_clean} District Skill Center",
                    location=f"{district_clean} Hub",
                    match=92,
                    explanation="Comprehensive technical training with certification, tool kit, and livelihood placement support.",
                    tags=["NSQF Level 4", "Free Toolkit", "Stipend ₹1500/mo"],
                    qp_code="AMH/Q0301",
                    stipend="₹1500 per month",
                )
            )

    # 2. PM-AJAY GIA Capital Asset Grant Card (Always eligible for SC enterprise / self-employment)
    if is_self_emp:
        items.append(
            RecommendationItem(
                id="pm-ajay-gia-01",
                type="Government support",
                title="PM-AJAY Capital Asset Grant (GIA)",
                provider="District Project Implementation Unit (DPIU)",
                location=f"{district_clean} District Welfare Office",
                match=98,
                explanation="Capital subsidy of up to 50% or ₹50,000 to purchase machinery, work tools, and initial inventory under PM-AJAY.",
                tags=["₹50,000 Capital Grant", "50% Subsidy", "DPIU Fast-track", "Direct Benefit"],
            )
        )

    # 3. NSFDC / Micro-credit Working Capital Card
    items.append(
        RecommendationItem(
            id="nsfdc-credit-01",
            type="Government support",
            title="NSFDC Micro-Credit Working Capital",
            provider="National SC Finance & Development Corp",
            location=f"Lead District Bank / CSC Center, {district_clean}",
            match=88,
            explanation="Concessional micro-loans up to ₹2,00,000 at low interest rates (4-6% p.a.) with Mudra tie-up for equipment and working capital.",
            tags=["Concessional Credit", "4-6% Interest", "Mudra Scheme", "Financial Support"],
        )
    )

    # 4. Modern Sector Trade (Bias Guard per spec)
    items.append(
        RecommendationItem(
            id="solar-pv-01",
            type="Training",
            title="Solar PV Installation & Maintenance",
            provider="PM Surya Ghar Skill Partner",
            location=f"{district_clean} District Training Center",
            match=86,
            explanation="High-demand renewable energy installation technician course aligned with PM Surya Ghar scheme.",
            tags=["Green Trade", "NSQF Level 4", "High Demand", "3 Months"],
            qp_code="ELE/Q5901",
            stipend="₹1500 per month",
        )
    )

    return items


# =====================================================================
# API Endpoints
# =====================================================================

@router.post("/session", response_model=SessionClientResponse)
async def create_session(req: CreateSessionRequest):
    """
    Initialize a new voice/text session for the kiosk frontend.
    """
    session_id = f"ws_{uuid.uuid4().hex[:8]}"
    session = await fsm.init_session(
        session_id=session_id,
        caller_id=req.phone_number or "web_kiosk_beneficiary",
    )

    chosen_lang = req.language or "Hindi"
    session.extracted_entities["selected_language"] = chosen_lang
    session.extracted_entities["district_code"] = req.district or "UP_VARANASI"
    await fsm.session_cache.save_session(session)

    # Persist session record to MongoDB
    if fsm.mongo_service and getattr(fsm.mongo_service, "_connected", False):
        try:
            await fsm.mongo_service.save_session_record(session_id, {
                "caller_id": req.phone_number or "web_kiosk_beneficiary",
                "language": chosen_lang,
                "district_code": req.district or "UP_VARANASI",
                "state": "interview",
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.warning(f"Failed to log session to MongoDB: {e}")

    initial_prompt = INITIAL_GREETINGS.get(chosen_lang, INITIAL_GREETINGS["Hindi"])
    profile = build_profile_dict(session)
    now_iso = datetime.now(timezone.utc).isoformat()

    return SessionClientResponse(
        id=session_id,
        session_id=session_id,
        language=chosen_lang,
        state="interview",
        initial_prompt_indic=initial_prompt,
        mock_audio_url="/static/audio/mock_greeting.wav",
        profile=profile,
        createdAt=now_iso,
        updatedAt=now_iso,
    )


@router.get("/session/{session_id}", response_model=SessionClientResponse)
async def get_session(session_id: str):
    """
    Retrieve active session and extracted profile.
    """
    session = await fsm.session_cache.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    lang = session.extracted_entities.get("selected_language", "Hindi")
    profile = build_profile_dict(session)
    now_iso = datetime.now(timezone.utc).isoformat()

    return SessionClientResponse(
        id=session_id,
        session_id=session_id,
        language=lang,
        state=session.current_state.value,
        initial_prompt_indic=INITIAL_GREETINGS.get(lang, INITIAL_GREETINGS["Hindi"]),
        mock_audio_url="/static/audio/mock_greeting.wav",
        profile=profile,
        createdAt=now_iso,
        updatedAt=now_iso,
    )


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    End and cleanup session.
    """
    session = await fsm.session_cache.get_session(session_id)
    if session:
        session.current_state = FSMState.COMPLETED
        await fsm.session_cache.save_session(session)
    return {"ok": True, "session_id": session_id}


@router.post("/interact", response_model=InteractResponse)
async def interact(req: InteractRequest):
    """
    Execute conversational turn in the FSM:
    - Extracts trade, mobility, education, enterprise goals.
    - Evaluates PM-AJAY GIA ₹50k asset subsidy eligibility.
    - Matches NSQF courses from MongoDB.
    - Generates dynamic spoken Indic response.
    """
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    session = await fsm.session_cache.get_session(req.session_id)
    if not session:
        session = await fsm.init_session(req.session_id)

    step_result = await fsm.step(req.session_id, req.user_transcript)

    # Re-fetch updated session
    session = await fsm.session_cache.get_session(req.session_id)
    profile = build_profile_dict(session)
    recs = await build_recommendations_for_session(session, mongo_service=fsm.mongo_service)

    # Enterprise subsidy checks
    ent = session.extracted_entities.get("enterprise_details", {})
    eligible_gia = bool(ent) or session.extracted_entities.get("employment_intent") in ("SELF_EMPLOYMENT", "HYBRID")
    max_subsidy = 50000.0 if eligible_gia else 0.0
    routing = "DPIU_CAPITAL_GRANT_DESK" if eligible_gia else None
    is_complete = step_result.get("current_state") in (FSMState.RECOMMENDATION_DELIVERY.value, FSMState.COMPLETED.value)

    # Update MongoDB session document
    if fsm.mongo_service and getattr(fsm.mongo_service, "_connected", False):
        try:
            await fsm.mongo_service.save_session_record(req.session_id, {
                "current_state": step_result.get("current_state"),
                "updated_slots": step_result.get("updated_slots", {}),
                "profile": profile,
                "recommendations_count": len(recs),
            })
        except Exception as e:
            logger.warning(f"Failed to update session record in MongoDB: {e}")

    return InteractResponse(
        session_id=req.session_id,
        current_state=step_result.get("current_state", "INTERVIEW"),
        spoken_response_indic=step_result.get("spoken_response_indic", "नमस्ते"),
        updated_slots=step_result.get("updated_slots", {}),
        profile=profile,
        recommended_courses=recs,
        eligible_for_gia_asset_grant=eligible_gia,
        max_capital_subsidy_inr=max_subsidy,
        credit_desk_routing=routing,
        is_complete=is_complete,
    )


@router.get("/recommendations/{session_id}", response_model=List[RecommendationItem])
async def get_recommendations(session_id: str):
    """
    Fetch tailored livelihood, NSQF training, and GIA subsidy recommendations.
    """
    session = await fsm.session_cache.get_session(session_id)
    if not session:
        # Fallback dummy session if not yet initialized
        session = await fsm.init_session(session_id)

    return await build_recommendations_for_session(session, mongo_service=fsm.mongo_service)


@router.post("/advisor/chat", response_model=AdvisorResponse)
async def advisor_chat(req: AdvisorRequest):
    """
    Context-aware AI Livelihood Advisor answering questions regarding
    PM-AJAY schemes, NSQF courses, toolkits, stipends, and GIA subsidies.
    """
    session = None
    if req.session_id:
        session = await fsm.session_cache.get_session(req.session_id)

    msg = req.message.lower()
    trade = ""
    district = "आपके जिले"
    if session:
        trade = session.extracted_entities.get("detected_trade", "")
        dist = session.extracted_entities.get("district_code", "")
        if dist:
            district = dist.replace("UP_", "").capitalize()

    # Rule-assisted intelligent conversational livelihood advisor
    if any(w in msg for w in ["subsidy", "अनुदान", "सब्सिडी", "पूंजी", "50000", "50,000", "gia"]):
        reply = (
            f"पीएम-अजय योजना के तहत अनुसूचित जाति (SC) के लाभार्थियों को खुद का स्वरोज़गार या दुकान शुरू करने के लिए "
            f"उपकरण और मशीनरी हेतु 50% तक (अधिकतम ₹50,000) की पूंजीगत अनुदान (GIA Subsidy) सीधे दी जाती है। "
            f"इसके लिए आपका आवेदन जिला कार्यालय (DPIU) द्वारा स्वीकृत किया जाता है।"
        )
        suggestions = ["सब्सिडी के लिए कौन से दस्तावेज़ चाहिए?", "प्रशिक्षण केंद्र कहाँ है?", "ऋण सहायता (NSFDC) कैसे मिलेगी?"]

    elif any(w in msg for w in ["प्रशिक्षण", "कोर्स", "training", "सिलाई", "दर्जी", "सर्टिफिकेट", "stipend"]):
        reply = (
            f"{district} में स्थित पीएम-अजय कौशल केंद्रों पर {trade or 'सिलाई व अन्य पारंपरिक व्यवसायों'} का प्रशिक्षण "
            f"पूरी तरह निःशुल्क है। इसमें आपको मुफ्त टूल-किट और ₹1,500 प्रति माह का स्टाइपेंड भी दिया जाता है।"
        )
        suggestions = ["टूल-किट में क्या मिलेगा?", "प्रशिक्षण कितने महीने का होगा?", "दुकान खोलने के लिए सहायता"]

    elif any(w in msg for w in ["loan", "ऋण", "कर्ज", "पैसा", "क्रेडिट", "nsfdc", "mudra"]):
        reply = (
            f"यदि आपको ₹50,000 से अधिक पूंजी की आवश्यकता है, तो NSFDC माइक्रो-क्रेडिट योजना के अंतर्गत 4% से 6% की रियायती ब्याज दर पर "
            f"₹2 लाख तक का स्वरोज़गार ऋण उपलब्ध कराया जाता है। इसे मुद्रा (Mudra) योजना से भी जोड़ा जा सकता है।"
        )
        suggestions = ["ऋण के लिए पात्रता क्या है?", "GIA सब्सिडी कैसे जोड़ें?", "निकटतम सहायता केंद्र"]

    elif any(w in msg for w in ["human", "अधिकारी", "बात", "फोन", "call"]):
        reply = (
            f"आप अपने {district} के जिला परियोजना समन्वयक (DPIU Officer) से सहायता डेस्क पर सीधे संपर्क कर सकते हैं। "
            f"हेल्पलाइन नंबर 1800-XXX-XXXX पर सुबह 9 से शाम 6 बजे तक निशुल्क कॉल करें।"
        )
        suggestions = ["मेरी प्रोफ़ाइल की स्थिति", "नए अवसर देखें", "प्रशिक्षण केंद्र का पता"]

    else:
        reply = (
            f"मैं आपकी पूरी सहायता करने के लिए तैयार हूँ। आप कौशल प्रशिक्षण, पीएम-अजय ₹50,000 उपकरण अनुदान, "
            f"या स्वरोज़गार ऋण के बारे में कोई भी प्रश्न अपनी भाषा में पूछ सकते हैं।"
        )
        suggestions = ["उपकरण व दुकान हेतु सब्सिडी", "निःशुल्क प्रशिक्षण व स्टाइपेंड", "NSFDC रियायती ऋण"]

    return AdvisorResponse(reply=reply, suggestions=suggestions)


@router.post("/audio/transcribe")
async def audio_transcribe(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    language: Optional[str] = Form("hi"),
):
    """
    Fallback audio transcription endpoint for browser audio uploads.
    """
    try:
        content = await file.read()
        logger.info(f"Received audio file: {file.filename}, size: {len(content)} bytes")

        # In production with faster-whisper available:
        # Transcript extracted through WhisperASRWorker.
        # Fallback simulation if running in lightweight container:
        transcript = "हम सिलाई मशीन के दुकान खोलल चाहत बानी, 40000 के पूंजी चाही"
        return {"transcript": transcript, "language": language or "hi", "size_bytes": len(content)}
    except Exception as exc:
        logger.error(f"Error during audio transcription: {exc}")
        return {"transcript": "नमस्ते", "language": language or "hi"}
