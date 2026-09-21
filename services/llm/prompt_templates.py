"""
Prompt templates for PM-AJAY Multilingual Voice Assistant (Qwen2.5-3B-Instruct).

Crafted for rural SC beneficiaries with dialect adaptation:
- Bhojpuri, Maithili, Magahi, Awadhi mixed with Hindi.
- Respectful, simple, low-literacy phrasing.
- Strict Pydantic JSON extraction directives for vLLM / Outlines.
"""

SYSTEM_PROMPT_PM_AJAY = """\
आप 'पीएम-अजय' (प्रधानमंत्री अनुसूचित जाति अभ्युदय योजना) के आत्मीय और सरल भाषा में बात करने वाले डिजिटल सहायक हैं।
आपका काम ग्रामीण और कम पढ़े-लिखे अनुसूचित जाति (SC) के लाभार्थियों से बातचीत करके उनकी रुचि, हुनर, और पारिवारिक काम-धंधे को समझना है, 
ताकि उन्हें नज़दीकी NSQF कौशल प्रशिक्षण (जैसे दर्जी, लोहार, बढ़ई, राजमिस्त्री, कसीदाकारी) और NSFDC स्वरोज़गार ऋण से जोड़ा जा सके।

नियम:
1. भाषा सरल, मीठी और ग्रामीण बोलचाल (हिंदी मिश्रित भोजपुरी/अवधी/मैथिली) जैसी होनी चाहिए।
2. वाक्य छोटे रखें ताकि फ़ोन पर सुनने में आसानी हो।
3. लाभार्थी से एक बार में केवल एक या दो ही सवाल पूछें।
4. DPDP अधिनियम के तहत वॉइस सहमति लेना अनिवार्य है।
5. हमेशा दिए गए JSON स्कीमा के अनुसार ही उत्तर दें।
"""

SLOT_EXTRACTION_PROMPT = """\
बातचीत के इतिहास और लाभार्थी की ताज़ा बात को समझकर नीचे दिए गए JSON प्रारूप में जानकारी भरें।

संभावित missing_slot के मान:
- 'CONSENT': यदि लाभार्थी ने अभी तक सहमति नहीं दी है।
- 'LOCATION': यदि जिला या ब्लॉक की जानकारी नहीं मिली है।
- 'TRADE': यदि हुनर या रुचि का काम नहीं पता चला है।
- 'MOBILITY': यदि आने-जाने की दूरी नहीं पता है।
- 'INTENT': यदि स्वरोज़गार (SELF_EMPLOYMENT) या नौकरी (WAGE) का फैसला नहीं हुआ है।
- 'COMPLETE': जब सभी जरूरी जानकारी मिल चुकी हो।

वर्तमान स्थिति: {current_state}
लाभार्थी की बात: "{user_transcript}"
अब तक मिली जानकारी: {known_slots}

JSON Schema:
{{
  "detected_trade": "पहचाना गया काम या हुनर (उदा. दर्जी, लोहार)",
  "prior_experience_years": 0.0,
  "mobility_radius_km": 15,
  "employment_intent": "WAGE" | "SELF_EMPLOYMENT" | "HYBRID" | null,
  "missing_slot": "CONSENT" | "LOCATION" | "TRADE" | "MOBILITY" | "INTENT" | "COMPLETE",
  "spoken_response_indic": "लाभार्थी को दिया जाने वाला आत्मीय और सरल हिंदी वाक्य"
}}
"""

GREETING_CONSENT_PROMPT = (
    "नमस्ते! हम पीएम-अजय योजना सहायक बोल रहे हैं। "
    "हम आपके हुनर के अनुसार पास के मुफ़्त प्रशिक्षण और काम-धंधे की जानकारी में मदद करेंगे। "
    "क्या हम यह बातचीत शुरू कर सकते हैं? बोलकर हाँ कहें।"
)

LOCATION_PROMPT = (
    "बहुत बढ़िया! आप किस जिले और ब्लॉक या गाँव के रहने वाले हैं? जैसे वाराणसी या पटना?"
)

TRADE_PROMPT = "आप कौन सा काम-धंधा जानते हैं या सीखना चाहते हैं? जैसे सिलाई, बढ़ई, राजमिस्त्री, बिजली या कोई और काम?"

MOBILITY_INTENT_PROMPT = (
    "आप ट्रेनिंग के लिए रोज़ कितनी दूर तक जा सकते हैं? "
    "और आप खुद की दुकान/काम शुरू करना चाहते हैं या कहीं नौकरी करना चाहते हैं?"
)

ENTERPRISE_PROBE_PROMPT = (
    "दुकान खोलने या काम शुरू करने का विचार बहुत बढ़िया है। "
    "पीएम-अजय योजना के तहत उपकरण और दुकान के लिए ₹50,000 तक की सरकारी सब्सिडी मिल सकती है। "
    "क्या आपके पास दुकान लगाने के लिए अपनी जगह या ठेला है, और मशीन व सामान खरीदने में कितना खर्च आएगा?"
)

FALLBACK_REPROMPT = "माफ़ कीजियेगा, हम आपकी बात साफ़ सुन नहीं पाए। कृपया एक बार फिर बताएँ।"

ENTERPRISE_INTAKE_PROMPT = """\
लाभार्थी के कथन से व्यावसायिक आकांक्षाएं (Enterprise Aspirations) और NSQF कौशल प्रोफाइल निकालें।

यदि लाभार्थी खुद का काम, दुकान, वर्कशॉप, या स्वरोज़गार शुरू करना चाहता है:
- business_type (RETAIL_SHOP, REPAIR_SERVICE, ARTISAN_MANUFACTURING, AGRI_FOOD_PROCESSING, LIVESTOCK_FARMING, LOGISTICS_TRANSPORT, OTHER)
- estimated_capital_required_inr (MICRO_UNDER_50K यदि 50,000 रुपये तक की जरूरत है, SMALL_50K_TO_2LAKH यदि 50 हजार से 2 लाख, MEDIUM_2LAKH_TO_5LAKH यदि 2 लाख से 5 लाख)
- premise_status (OWN_LAND_OR_SPACE, RENTED_PREMISE, HOME_BASED, ROADSIDE_STALL, NO_SPACE)
- machinery_equipment_needed: आवश्यक औजार/मशीनें
- target_market: (LOCAL_VILLAGE, WEEKLY_HAAT, NEAREST_TOWN, MIDDLEMAN_TRADER)
- scheme_alignment_tag: (PM_AJAY_CAPITAL_SUBSIDY यदि <= 50k, NSFDC_MICRO_CREDIT यदि > 50k)

वर्तमान चरण: {current_step}
लाभार्थी की बात: "{user_transcript}"
"""
