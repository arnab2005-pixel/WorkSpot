"""
LLM and prompt management module for PM-AJAY Voice Assistant.
"""

from .prompt_templates import (
    FALLBACK_REPROMPT,
    GREETING_CONSENT_PROMPT,
    LOCATION_PROMPT,
    MOBILITY_INTENT_PROMPT,
    SLOT_EXTRACTION_PROMPT,
    SYSTEM_PROMPT_PM_AJAY,
    TRADE_PROMPT,
)
from .vllm_client import VLLMClient

__all__ = [
    "FALLBACK_REPROMPT",
    "GREETING_CONSENT_PROMPT",
    "LOCATION_PROMPT",
    "MOBILITY_INTENT_PROMPT",
    "SLOT_EXTRACTION_PROMPT",
    "SYSTEM_PROMPT_PM_AJAY",
    "TRADE_PROMPT",
    "VLLMClient",
]
