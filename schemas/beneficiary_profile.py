"""
Beneficiary Enterprise Profiling Schemas for PM-AJAY Voice Virtual Assistant.

Captures enterprise aspirations under PM-AJAY Grant-in-Aid (GIA) capital subsidy
(up to 50% or ₹50,000) and linkages with NSFDC and PM Mudra micro-credit schemes.
"""

from typing import Literal

from pydantic import BaseModel, Field


class EnterpriseAspirations(BaseModel):
    """
    Enterprise and self-employment profiling slots under PM-AJAY GIA and NSFDC.
    """

    is_interested_in_business: bool = Field(
        ..., description="Whether beneficiary wants to launch or expand an enterprise"
    )
    business_type: (
        Literal[
            "RETAIL_SHOP",  # Kirana, tailoring shop, footwear retail
            "REPAIR_SERVICE",  # Mobile repair, auto-garage, appliance servicing
            "ARTISAN_MANUFACTURING",  # Leather goods, handloom, pottery, carpentry workshop
            "AGRI_FOOD_PROCESSING",  # Flour mill, spice packaging, pickle making, dairy
            "LIVESTOCK_FARMING",  # Goat farming, poultry, piggery, pisciculture
            "LOGISTICS_TRANSPORT",  # E-rickshaw, cargo auto, rural courier
            "OTHER",
        ]
        | None
    ) = Field(None, description="Broad enterprise vertical")

    enterprise_model: (
        Literal["INDIVIDUAL", "FAMILY_RUN", "SHG_COOPERATIVE", "PARTNERSHIP"] | None
    ) = Field(None, description="Operating structure of the business")

    estimated_capital_required_inr: (
        Literal[
            "MICRO_UNDER_50K",  # Covered fully by PM-AJAY GIA subsidy + margin
            "SMALL_50K_TO_2LAKH",  # Requires NSFDC Micro-Credit / Mudra Shishu
            "MEDIUM_2LAKH_TO_5LAKH",  # Requires Mudra Kishore / Term Loan
            "UNSURE",
        ]
        | None
    ) = Field(None, description="Estimated seed capital range mentioned by caller")

    own_investment_capacity_inr: int | None = Field(
        None, ge=0, description="Self-contribution / margin money available (if stated)"
    )

    premise_status: (
        Literal[
            "OWN_LAND_OR_SPACE",
            "RENTED_PREMISE",
            "HOME_BASED",
            "ROADSIDE_STALL",
            "NO_SPACE",
        ]
        | None
    ) = Field(None, description="Physical location readiness for the shop/unit")

    machinery_equipment_needed: list[str] = Field(
        default_factory=list,
        description="Tools required (e.g., ['motorized_sewing_machine', 'shoe_finishing_bench'])",
    )

    shg_membership: bool | None = Field(
        None,
        description="Whether the applicant or household belongs to a NRLM Self-Help Group",
    )

    target_market: (
        Literal["LOCAL_VILLAGE", "WEEKLY_HAAT", "NEAREST_TOWN", "MIDDLEMAN_TRADER"]
        | None
    ) = Field(None, description="Where goods or services will be sold")

    scheme_alignment_tag: (
        Literal[
            "PM_AJAY_CAPITAL_SUBSIDY",
            "NSFDC_MAHILA_SAMRIDDHI",
            "NSFDC_MICRO_CREDIT",
            "MUDRA_SHISHU",
            "STAND_UP_INDIA",
        ]
        | None
    ) = Field(None, description="Automated classification for target financial scheme")


class ProfileSlots(BaseModel):
    """
    Consolidated vocational profile including Sector Skill Council mapping and enterprise goals.
    """

    detected_trade: str | None = Field(
        None, description="Identified artisan, trade, or vocational craft"
    )
    standardized_sector: (
        Literal[
            "Apparel, Made-Ups & Home Furnishing",
            "Leather & Leather Goods",
            "Construction & Masonry",
            "Automotive & Fabrication",
            "Agriculture & Food Processing",
            "Electronics & Hardware",
            "Handicrafts & Carpet",
            "Beauty & Wellness",
            "Unskilled / General",
            "Other",
        ]
        | None
    ) = Field(None, description="Mapped Sector Skill Council (SSC) domain")

    prior_experience_years: float | None = Field(None, ge=0.0)
    education_level: (
        Literal["none", "class_5", "class_8", "class_10", "class_12", "graduate"] | None
    ) = Field(None)

    mobility_radius_km: int | None = Field(
        None, ge=0, le=100, description="0 indicates home-bound or village-only"
    )
    employment_intent: (
        Literal["WAGE_EMPLOYMENT", "SELF_EMPLOYMENT", "HYBRID"] | None
    ) = Field(None)

    enterprise_details: EnterpriseAspirations | None = Field(
        None,
        description="Populated whenever employment_intent includes SELF_EMPLOYMENT or HYBRID",
    )


class DialogueState(BaseModel):
    """
    FSM tracking state for enterprise scoping dialogue.
    """

    current_step: Literal[
        "CONSENT",
        "LOCATION",
        "TRADE_DISCOVERY",
        "ENTERPRISE_SCOPING",
        "MOBILITY_CHECK",
        "COMPLETE",
    ]
    missing_slots: list[str]
    is_profile_complete: bool
    requires_human_escalation: bool = False


class ConversationalResponse(BaseModel):
    """
    Dialect-aware spoken output and next conversational action.
    """

    spoken_text_indic: str = Field(
        ..., description="Dialect-aware conversational reply in Hindi"
    )
    target_action: Literal[
        "PROBE_TRADE",
        "PROBE_ENTERPRISE_CAPITAL",
        "PROBE_PREMISE",
        "PROBE_MOBILITY",
        "DELIVER_COURSE_MATCH",
        "HANGUP",
    ]


class LLMIntakePayload(BaseModel):
    """
    Structured intake output produced by local Qwen2.5-3B-Instruct via Outlines/vLLM.
    """

    profile_slots: ProfileSlots
    dialogue_state: DialogueState
    conversational_response: ConversationalResponse
