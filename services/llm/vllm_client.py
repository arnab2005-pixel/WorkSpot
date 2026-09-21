"""
vLLM Client interfacing with Qwen2.5-3B-Instruct for Outlines/Pydantic structured decoding.

Connects to http://127.0.0.1:8000/v1 with response_format constraints matching ExtractedSlots.
Includes rule-based fallback when vLLM is offline or during testing.
"""

import json
import logging
import os
import re
import time
from typing import Any

import httpx
from pydantic import ValidationError

from config.config import get_settings
from schemas.beneficiary_profile import (
    ConversationalResponse,
    DialogueState,
    EnterpriseAspirations,
    LLMIntakePayload,
    ProfileSlots,
)
from schemas.session import ExtractedSlots
from services.llm.prompt_templates import (
    ENTERPRISE_INTAKE_PROMPT,
    SLOT_EXTRACTION_PROMPT,
    SYSTEM_PROMPT_PM_AJAY,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class VLLMClient:
    """
    Client for vLLM server serving Qwen2.5-3B-Instruct with structured JSON schema decoding.
    Supports Gemini API fallback when local vLLM is offline/unreachable.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        timeout: float | None = None,
    ):
        self.base_url = (base_url or settings.vllm_base_url).rstrip("/")
        self.model_name = model_name or settings.vllm_model_name
        self.timeout = timeout or settings.vllm_timeout_seconds
        self.schema_json = ExtractedSlots.model_json_schema()

    async def _call_gemini_api(
        self, system_prompt: str, user_prompt: str
    ) -> str | None:
        """
        Call Gemini API fallback when local vLLM is unreachable.
        Uses GEMINI_API_KEY environment variable or settings.
        """
        api_key = settings.gemini_api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return None

        model = settings.gemini_model or "gemini-2.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        try:
            async with httpx.AsyncClient(
                timeout=settings.gemini_timeout_seconds
            ) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return text
        except Exception as exc:  # noqa: BLE001 - provider fallback must handle runtime failures
            logger.warning("Gemini API fallback call failed: %s", exc)
            return None

    async def extract_slots(
        self,
        user_transcript: str,
        current_state: str,
        known_slots: dict[str, Any] | None = None,
    ) -> ExtractedSlots:
        """
        Extract conversational slots and produce dialect-friendly next response.

        Uses vLLM /v1/chat/completions with json_schema constraint.
        Falls back to Gemini API (if GEMINI_API_KEY is present) or rule-based extractor if unreachable.
        """
        known_slots = known_slots or {}
        user_prompt = SLOT_EXTRACTION_PROMPT.format(
            current_state=current_state,
            user_transcript=user_transcript,
            known_slots=json.dumps(known_slots, ensure_ascii=False),
        )

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_PM_AJAY},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 512,
            "response_format": {
                "type": "json_object",
                "schema": self.schema_json,
            },
        }

        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                logger.info(f"vLLM response received in {elapsed_ms:.1f}ms")

                content = data["choices"][0]["message"]["content"]
                parsed_json = json.loads(content)
                return ExtractedSlots.model_validate(parsed_json)

        except (
            httpx.HTTPError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            logger.warning(
                "vLLM server call failed (%s). Trying Gemini API fallback...",
                exc,
            )
            gemini_text = await self._call_gemini_api(
                SYSTEM_PROMPT_PM_AJAY, user_prompt
            )
            if gemini_text:
                try:
                    parsed_json = json.loads(gemini_text)
                    logger.info("Successfully extracted slots via Gemini API fallback")
                    return ExtractedSlots.model_validate(parsed_json)
                except Exception as g_err:  # noqa: BLE001 - provider fallback must handle runtime failures
                    logger.warning(
                        "Failed to parse Gemini API JSON response: %s", g_err
                    )

            logger.warning("Falling back to local slot extractor.")
            return self._fallback_extract(user_transcript, current_state, known_slots)

    def _fallback_extract(
        self,
        transcript: str,
        current_state: str,
        known_slots: dict[str, Any],
    ) -> ExtractedSlots:
        """
        Deterministic rule-based fallback for tests, offline dev, or vLLM outages.
        """
        t = transcript.lower()

        # Trade detection keywords
        trade = known_slots.get("detected_trade")
        if not trade:
            if any(w in t for w in ["सिलाई", "दर्जी", "कपड़ा", "tailor", "sewing"]):
                trade = "सिलाई / Tailoring"
            elif any(w in t for w in ["लोहार", "लोहा", "blacksmith"]):
                trade = "लोहार / Blacksmith"
            elif any(w in t for w in ["बढ़ई", "लकड़ी", "carpenter"]):
                trade = "बढ़ई / Carpenter"
            elif any(w in t for w in ["राजमिस्त्री", "मिस्त्री", "मकान", "mason"]):
                trade = "राजमिस्त्री / Mason"
            elif any(w in t for w in ["कसीदाकारी", "कढ़ाई", "embroidery"]):
                trade = "कसीदाकारी / Embroidery"
            elif any(w in t for w in ["बिजली", "इलेक्ट्रीशियन", "wireman"]):
                trade = "बिजली मिस्त्री / Electrician"

        # Mobility detection
        mobility = known_slots.get("mobility_radius_km", 15)
        mobility_matches = re.findall(r"(\d+)\s*(किलोमीटर|किमी|km)", t)
        if mobility_matches:
            try:
                mobility = int(mobility_matches[0][0])
            except ValueError:
                pass

        # Employment intent
        intent = known_slots.get("employment_intent")
        if not intent:
            if any(w in t for w in ["दुकान", "खुद का", "स्वरोज़गार", "बिजनेस", "अपना"]):
                intent = "SELF_EMPLOYMENT"
            elif any(w in t for w in ["नौकरी", "फैक्ट्री", "काम करना"]):
                intent = "WAGE"
            elif any(w in t for w in ["दोनों", "कुछ भी"]):
                intent = "HYBRID"

        # Determine missing slot and next prompt based on current state
        if current_state == "INIT_CONSENT" or known_slots.get("consent") is not True:
            if any(w in t for w in ["हाँ", "हां", "ठीक", "शुरू", "yes", "sure", "बताईं"]):
                missing_slot = "LOCATION"
                spoken_response = (
                    "बहुत बढ़िया! आप किस जिले और ब्लॉक के रहने वाले हैं? जैसे वाराणसी या चंदौली?"
                )
            else:
                missing_slot = "CONSENT"
                spoken_response = (
                    "क्या हम पीएम-अजय योजना के बारे में आगे बात कर सकते हैं? कृपया हाँ कहें।"
                )

        elif current_state == "GEOGRAPHIC_INTAKE" or not known_slots.get(
            "district_code"
        ):
            missing_slot = "TRADE"
            spoken_response = "आप कौन सा हुनर या काम-धंधा जानते हैं या सीखना चाहते हैं? जैसे सिलाई, बढ़ई या राजमिस्त्री?"

        elif current_state == "VOCATIONAL_DISCOVERY" or not trade:
            if trade:
                missing_slot = "MOBILITY"
                spoken_response = f"{trade} का काम बहुत अच्छा है! आप रोज़ सीखने के लिए कितनी दूर जा सकते हैं, और खुद का काम शुरू करना चाहते हैं या नौकरी?"
            else:
                missing_slot = "TRADE"
                spoken_response = "कृपया बताएँ आप किस काम में रुचि रखते हैं, जैसे सिलाई, लोहार, बढ़ई या राजमिस्त्री?"

        elif current_state == "MOBILITY_AND_INTENT" or not intent:
            if intent:
                missing_slot = "COMPLETE"
                spoken_response = "धन्यवाद! आपकी जानकारी के आधार पर आपके नज़दीक दो प्रशिक्षण केंद्र और ऋण विकल्प उपलब्ध हैं।"
            else:
                missing_slot = "INTENT"
                spoken_response = "आप खुद की दुकान शुरू करने के लिए लोन चाहते हैं या किसी कंपनी में नौकरी करना चाहते हैं?"

        else:
            missing_slot = "COMPLETE"
            spoken_response = (
                "आपकी पूरी जानकारी दर्ज कर ली गई है। नज़दीकी केंद्र की जानकारी पेश की जा रही है।"
            )

        return ExtractedSlots(
            detected_trade=trade,
            prior_experience_years=float(
                known_slots.get("prior_experience_years", 0.0)
            ),
            mobility_radius_km=int(mobility),
            employment_intent=intent,
            missing_slot=missing_slot,
            spoken_response_indic=spoken_response,
        )

    async def extract_enterprise_intake(
        self,
        user_transcript: str,
        current_step: str = "TRADE_DISCOVERY",
    ) -> LLMIntakePayload:
        """
        Extract detailed enterprise aspirations and produce dialect-aware conversational response.
        Guided by LLMIntakePayload schema via vLLM.
        """
        user_prompt = ENTERPRISE_INTAKE_PROMPT.format(
            current_step=current_step,
            user_transcript=user_transcript,
        )

        guided_json = LLMIntakePayload.model_json_schema()
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_PM_AJAY},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 768,
            "response_format": {
                "type": "json_object",
                "schema": guided_json,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions", json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return LLMIntakePayload.model_validate_json(content)
        except (
            httpx.HTTPError,
            KeyError,
            IndexError,
            TypeError,
            ValueError,
            ValidationError,
        ) as exc:
            logger.warning(
                "vLLM enterprise intake call failed: %s. "
                "Running dialect fallback parser.",
                exc,
            )
            return self._fallback_extract_enterprise(user_transcript, current_step)

    def _fallback_extract_enterprise(
        self,
        transcript: str,
        current_step: str,
    ) -> LLMIntakePayload:
        """
        Dialect-aware fallback parser for enterprise and rural vocational intake.
        Handles mixed Bhojpuri / Maithili / Awadhi / Hindi idioms.
        """
        t = transcript.lower()

        # Trade and Sector Detection
        trade = "सामान्य कौशल / General Trade"
        sector = "Other"
        machinery: list[str] = []

        if any(w in t for w in ["चमड़ा", "जूता", "चर्मकार", "leather", "chamar", "shoe"]):
            trade = "चर्मकार / जूता निर्माण एवं मरम्मत (Leather Craft)"
            sector = "Leather & Leather Goods"
            machinery = ["shoe_sewing_machine", "leather_sole_finisher"]
        elif any(w in t for w in ["सिलाई", "दर्जी", "कपड़ा", "tailor", "sewing"]):
            trade = "सिलाई एवं परिधान (Tailoring & Garments)"
            sector = "Apparel, Made-Ups & Home Furnishing"
            machinery = ["motorized_sewing_machine", "overlock_machine"]
        elif any(w in t for w in ["लोहार", "लोहा", "blacksmith", "वेल्डिंग"]):
            trade = "लोहार एवं वेल्डिंग (Blacksmith / Welding)"
            sector = "Automotive & Fabrication"
            machinery = ["welding_machine", "grinder"]
        elif any(w in t for w in ["बढ़ई", "लकड़ी", "carpenter", "फर्नीचर"]):
            trade = "बढ़ईगीरी (Carpentry & Woodwork)"
            sector = "Handicrafts & Carpet"
            machinery = ["circular_saw", "wood_planner"]
        elif any(w in t for w in ["राजमिस्त्री", "मिस्त्री", "मकान", "mason"]):
            trade = "राजमिस्त्री (Masonry)"
            sector = "Construction & Masonry"
            machinery = ["concrete_mixer", "trowel_set"]

        # Capital requirement parsing (e.g. 25-30 हजार, 50 हजार, 1 लाख)
        capital_tag = "MICRO_UNDER_50K"
        scheme_tag = "PM_AJAY_CAPITAL_SUBSIDY"
        if any(w in t for w in ["लाख", "1 लाख", "2 लाख", "50k to 2lakh"]):
            capital_tag = "SMALL_50K_TO_2LAKH"
            scheme_tag = "NSFDC_MICRO_CREDIT"
        elif any(w in t for w in ["3 लाख", "4 लाख", "5 लाख"]):
            capital_tag = "MEDIUM_2LAKH_TO_5LAKH"
            scheme_tag = "STAND_UP_INDIA"
        elif any(
            w in t
            for w in ["25-30", "25 हजार", "30 हजार", "40 हजार", "50 हजार", "हजार"]
        ):
            capital_tag = "MICRO_UNDER_50K"
            scheme_tag = "PM_AJAY_CAPITAL_SUBSIDY"

        # Premise status
        premise = "OWN_LAND_OR_SPACE"
        if any(w in t for w in ["बजारिए", "बाजार", "ठेला", "stall", "roadside", "सड़क"]):
            premise = "ROADSIDE_STALL"
        elif any(w in t for w in ["घर", "घरै", "home"]):
            premise = "HOME_BASED"
        elif any(w in t for w in ["किराया", "rent"]):
            premise = "RENTED_PREMISE"

        # Market access
        market = "LOCAL_VILLAGE"
        if any(w in t for w in ["बजारिए", "बाजार", "हाट", "haat", "पैठ"]):
            market = "WEEKLY_HAAT"
        elif any(w in t for w in ["शहर", "town"]):
            market = "NEAREST_TOWN"

        # Mobility
        mobility = 5
        if any(w in t for w in ["शहर ना", "गांव के", "गांव"]):
            mobility = 5

        # Experience
        exp = 1.0
        if any(w in t for w in ["बाबूजी", "खानदानी", "थोड़ा-बहुत", "साल", "सी लेईला"]):
            exp = 3.0

        enterprise = EnterpriseAspirations(
            is_interested_in_business=True,
            business_type="REPAIR_SERVICE"
            if "मरम्मत" in trade or "जूता" in trade
            else "RETAIL_SHOP",
            enterprise_model="INDIVIDUAL",
            estimated_capital_required_inr=capital_tag,
            own_investment_capacity_inr=None,
            premise_status=premise,
            machinery_equipment_needed=machinery,
            shg_membership=None,
            target_market=market,
            scheme_alignment_tag=scheme_tag,
        )

        profile_slots = ProfileSlots(
            detected_trade=trade,
            standardized_sector=sector,
            prior_experience_years=exp,
            education_level=None,
            mobility_radius_km=mobility,
            employment_intent="SELF_EMPLOYMENT",
            enterprise_details=enterprise,
        )

        dialogue_state = DialogueState(
            current_step="ENTERPRISE_SCOPING",
            missing_slots=["EDUCATION", "PREMISE_CONFIRMATION"],
            is_profile_complete=False,
            requires_human_escalation=False,
        )

        conversational_response = ConversationalResponse(
            spoken_text_indic=(
                "दुकान खोलने का विचार बहुत बढ़िया है। पीएम-अजय योजना के तहत उपकरण और दुकान के लिए "
                "₹50,000 तक की सरकारी मदद मिल सकती है। क्या आपके पास बाज़ार में दुकान लगाने के लिए अपनी जगह या ठेला है, "
                "या किराए पर लेना होगा?"
            ),
            target_action="PROBE_PREMISE",
        )

        return LLMIntakePayload(
            profile_slots=profile_slots,
            dialogue_state=dialogue_state,
            conversational_response=conversational_response,
        )
