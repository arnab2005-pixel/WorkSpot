"""
DPIU Application pre-fill data models for PM-AJAY Voice Assistant.

Captures pre-filled capital subsidy (PM-AJAY GIA) and micro-credit applications
generated from successful conversational interactions.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DpiuApplicationRecord(BaseModel):
    """Pre-filled beneficiary application for DPIU / NSFDC portal processing."""

    model_config = ConfigDict(populate_by_name=True)

    application_id: str = Field(
        ..., description="Unique application identifier e.g. 'DPIU-UP-VAR-2026-0001'"
    )
    phone_hash: str = Field(..., description="Salted SHA-256 phone hash of beneficiary")
    district_code: str = Field(..., description="LGD district identifier")
    block_name: str | None = None

    # Vocational & Enterprise details
    selected_trade: str = Field(
        ..., description="Selected vocational trade / enterprise"
    )
    recommended_course_qp: str | None = Field(
        None, description="Recommended NSQF QP code"
    )

    # Financial scheme alignment
    subsidy_scheme: Literal[
        "PM_AJAY_GIA_CAPITAL_GRANT",
        "NSFDC_MICRO_CREDIT",
        "NSFDC_MAHILA_SAMRIDDHI",
        "MUDRA_KISHORE",
        "OTHER",
    ] = Field(default="PM_AJAY_GIA_CAPITAL_GRANT")

    requested_asset: str | None = Field(
        None, description="Machinery / tool-kit requested"
    )
    estimated_capital_inr: int = Field(default=0, ge=0)
    subsidy_eligible_amount_inr: int = Field(default=0, ge=0)

    # DPDP Audit proof
    voice_consent_audio_vault_ref: str = Field(
        ..., description="Audio vault reference of explicit consent"
    )

    # Status
    status: Literal[
        "PREFILL_GENERATED",
        "DISPATCHED_TO_DPIU_PORTAL",
        "UNDER_VERIFICATION",
        "APPROVED",
        "REJECTED",
    ] = Field(default="PREFILL_GENERATED")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
