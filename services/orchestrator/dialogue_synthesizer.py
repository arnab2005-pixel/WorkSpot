"""
Context-Chained Dialogue Synthesizer for PM-AJAY Voice Assistant.

Implements the dynamic 3-part conversational synthesis pattern:
Next Turn = [Empathetic Acknowledgement] + [Entity Hook / Bridge] + [Target Inquiry]
and generates contextual interactive MCQ options for touch or voice input.
"""

import re
import logging
from typing import Optional, Tuple, List
import httpx

from schemas.session import DynamicChainedState, FSMState

logger = logging.getLogger(__name__)

FALLBACK_REPROMPT = (
    "माफ़ कीजियेगा, आवाज़ साफ़ नहीं आई। कृपया अपनी बात दोबारा कहें ताकि हम सही योजना ढूंढ सकें।"
)


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
                "ठेकेदारी / खुद की लेबर टीम",
                "बिल्डर के साथ पक्की नौकरी",
            ]
            return f"{ack} {hook} {inquiry}", options

        elif is_unskilled:
            ack = "हर दिन मेहनत करके परिवार संभालना बहुत सम्मान की बात है।"
            hook = "पीएम-अजय योजना से आप 15 दिन में पक्का हुनर सीखकर अपनी आय दोगुनी कर सकते हैं—"
            inquiry = "आप बिजली का काम, मोटर रिपेयरिंग या सिलाई में से क्या सीखना पसंद करेंगे?"
            options = [
                "बिजली व वायरिंग",
                "सोलर पैनल रिपेयर",
                "सिलाई / टेलरिंग",
                "ड्राइविंग / ऑटो मैकेनिक",
            ]
            return f"{ack} {hook} {inquiry}", options

        elif is_tailoring:
            years_match = re.search(r"(\d+)\s*(साल|वर्ष|year)", user_transcript)
            years_str = f"{years_match.group(1)} साल" if years_match else "पुराना"
            ack = f"{years_str} का सिलाई का तजुर्बा तो बहुत काम आएगा!"
            hook = (
                f"क्या आप किसी गारमेंट फैक्ट्री में पक्की नौकरी करना पसंद करेंगे, या "
                f"{state.block or 'पिंडरा'} बाज़ार में अपनी खुद की सिलाई की दुकान खोलना चाहेंगे?"
            )
            inquiry = "अपनी खुद की दुकान खोलना चाहेंगे या फैक्ट्री में नौकरी?"
            options = [
                f"{state.block or 'पिंडरा'} बाज़ार में अपनी दुकान",
                "गारमेंट फैक्ट्री में नौकरी",
                "घर पर सिलाई का काम",
                "अन्य",
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
        # Fallback to Gemini API if GEMINI_API_KEY is configured
        from config.config import get_settings
        import os
        cfg = get_settings()
        api_key = cfg.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                model = cfg.gemini_model or "gemini-2.5-flash"
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 80},
                }
                async with httpx.AsyncClient(timeout=timeout_s) as client:
                    g_resp = await client.post(g_url, json=payload)
                    if g_resp.status_code == 200:
                        g_data = g_resp.json()
                        return g_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as g_exc:
                logger.warning("Gemini API question generation fallback failed: %s", g_exc)
    return None
