"""
LLM and prompt management module for PM-AJAY Voice Assistant.
"""

from .prompt_templates import (
    SYSTEM_PROMPT_PM_AJAY,
    SLOT_EXTRACTION_PROMPT,
    GREETING_CONSENT_PROMPT,
    LOCATION_PROMPT,
    TRADE_PROMPT,
    MOBILITY_INTENT_PROMPT,
    FALLBACK_REPROMPT,
)
from .vllm_client import VLLMClient

__all__ = [
    "SYSTEM_PROMPT_PM_AJAY",
    "SLOT_EXTRACTION_PROMPT",
    "GREETING_CONSENT_PROMPT",
    "LOCATION_PROMPT",
    "TRADE_PROMPT",
    "MOBILITY_INTENT_PROMPT",
    "FALLBACK_REPROMPT",
    "VLLMClient",
]
