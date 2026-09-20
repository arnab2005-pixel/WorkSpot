"""
Beneficiary data models for PM-AJAY Voice Assistant.

These models represent the beneficiary profile stored in MongoDB.
All sensitive data (phone numbers) are stored as salted hashes.
"""

from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator
import hashlib
import secrets


class Demographics(BaseModel):
    """Geographic and demographic information."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "district_code": "UP_VARANASI",
                "block_name": "Chiraigaon",
                "age_bracket": "25-35",
                "education_level": "class_8"
            }
        }
    )
    
    district_code: str = Field(
        ..., 
        description="LGD district identifier (e.g., 'UP_VARANASI', 'BR_PATNA')",
        min_length=2,
        max_length=50
    )
    block_name: Optional[str] = Field(
        None, 
        description="Block/Tehsil name within district",
        max_length=100
    )
    age_bracket: Optional[str] = Field(
        None, 
        description="Age bracket: '18-25', '25-35', '35-45', '45-60', '60+'",
        pattern=r"^(18-25|25-35|35-45|45-60|60\+)$"
    )
    education_level: str = Field(
        ..., 
        description="e.g., 'none', 'class_5', 'class_8', 'class_10'"
    )


class ProfilingSlots(BaseModel):
    """Vocational profiling slots collected during conversation."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "traditional_trade": "सिलाई / Tailoring",
                "current_activity": "गृहिणी / Homemaker",
                "mobility_radius_km": 15,
                "employment_intent": "SELF_EMPLOYMENT",
                "prior_experience": True
            }
        }
    )
    
    traditional_trade: Optional[str] = Field(
        None, 
        description="Family/traditional artisanal trade (Hindi/English)",
        max_length=100
    )
    current_activity: Optional[str] = Field(
        None, 
        description="Current primary activity",
        max_length=100
    )
    mobility_radius_km: int = Field(
        default=15, 
        description="Maximum daily commute radius in kilometers",
        ge=0,
        le=100
    )
    employment_intent: Literal["WAGE", "SELF_EMPLOYMENT", "HYBRID"] = Field(
        ..., 
        description="Employment preference"
    )
    prior_experience: bool = Field(
        default=False, 
        description="Whether beneficiary has prior experience in the trade"
    )


class ConsentAudit(BaseModel):
    """DPDP Act compliant consent audit trail."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "voice_verified": True,
                "consent_timestamp": "2026-09-20T10:00:00Z",
                "audio_vault_ref": "s3://pm-ajay-consent/sess_abc123_consent.wav"
            }
        }
    )
    
    voice_verified: bool = Field(
        ..., 
        description="Whether voice consent was explicitly captured and verified"
    )
    consent_timestamp: datetime = Field(
        ..., 
        description="ISO 8601 timestamp when consent was given"
    )
    audio_vault_ref: str = Field(
        ..., 
        description="Reference to stored consent audio (S3/GCS path)",
        max_length=500
    )
    consent_version: str = Field(
        default="1.0",
        description="Consent form version"
    )
    language: str = Field(
        default="hi",
        description="Language in which consent was given"
    )


class BeneficiaryRecord(BaseModel):
    """Complete beneficiary record stored in MongoDB."""
    
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "phone_hash": "a1b2c3d4e5f6...",
                "preferred_language": "hi",
                "detected_dialect": "bhojpuri_mixed",
                "demographics": {
                    "district_code": "UP_VARANASI",
                    "block_name": "Chiraigaon",
                    "age_bracket": "25-35",
                    "education_level": "class_8"
                },
                "profiling_slots": {
                    "traditional_trade": "सिलाई / Tailoring",
                    "current_activity": "गृहिणी / Homemaker",
                    "mobility_radius_km": 15,
                    "employment_intent": "SELF_EMPLOYMENT",
                    "prior_experience": True
                },
                "consent_audit": {
                    "voice_verified": True,
                    "consent_timestamp": "2026-09-20T10:00:00Z",
                    "audio_vault_ref": "s3://pm-ajay-consent/sess_abc123_consent.wav"
                },
                "created_at": "2026-09-20T10:00:00Z"
            }
        }
    )
    
    # Identity (hashed, never store raw phone)
    phone_hash: str = Field(
        ..., 
        description="SHA-256 salted hash of mobile number",
        min_length=64,
        max_length=128
    )
    salt: Optional[str] = Field(
        default=None, 
        description="Salt used for phone hash"
    )
    
    # Language preferences
    preferred_language: str = Field(
        default="hi", 
        description="Preferred language ISO code",
        pattern=r"^(hi|bho|mai|mag|awa)$"
    )
    detected_dialect: Optional[str] = Field(
        default="bhojpuri_mixed", 
        description="Detected dialect variant",
        max_length=50
    )
    
    # Profile data
    demographics: Demographics
    profiling_slots: ProfilingSlots
    consent_audit: ConsentAudit
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_call_at: Optional[datetime] = None
    total_calls: int = Field(default=0, ge=0)
    
    # Enrollment tracking
    enrolled_course_qp_codes: List[str] = Field(default_factory=list)
    active_enrollment_id: Optional[str] = None
    
    # PM-AJAY GIA Capital Subsidy & Enterprise Routing
    enterprise_details: Optional[dict] = Field(default=None, description="Enterprise aspirations details")
    eligible_for_gia_asset_grant: bool = Field(default=False, description="Flagged for PM-AJAY GIA capital subsidy (up to 50k)")
    credit_desk_routing: Optional[str] = Field(default=None, description="Routed credit desk (e.g. NSFDC_MICRO_CREDIT, MUDRA_KISHORE)")
    dpiu_prefill_status: Optional[str] = Field(default=None, description="Status of pre-filled application push to DPIU")
    
    @field_validator("phone_hash", mode="before")
    @classmethod
    def validate_phone_hash(cls, v: str) -> str:
        if len(v) < 64:
            raise ValueError("Phone hash must be at least 64 characters (SHA-256 hex)")
        return v.lower()
    
    @classmethod
    def create_phone_hash(cls, phone_number: str, salt: Optional[str] = None) -> tuple[str, str]:
        """
        Create a salted SHA-256 hash of a phone number.
        
        Args:
            phone_number: Raw phone number (e.g., "+919876543210")
            salt: Optional salt (generated if not provided)
            
        Returns:
            Tuple of (hash_hex, salt_hex)
        """
        if salt is None:
            salt = secrets.token_hex(32)
        
        # Normalize phone number
        normalized = phone_number.strip().replace(" ", "").replace("-", "")
        if not normalized.startswith("+91"):
            if normalized.startswith("91"):
                normalized = "+" + normalized
            elif normalized.startswith("0"):
                normalized = "+91" + normalized[1:]
            else:
                normalized = "+91" + normalized
        
        # Hash with salt
        hash_obj = hashlib.sha256()
        hash_obj.update(salt.encode())
        hash_obj.update(normalized.encode())
        
        return hash_obj.hexdigest(), salt
    
    @classmethod
    def verify_phone(cls, phone_number: str, phone_hash: str, salt: str) -> bool:
        """Verify a phone number against stored hash and salt."""
        computed_hash, _ = cls.create_phone_hash(phone_number, salt)
        return computed_hash == phone_hash


class BeneficiaryCreate(BaseModel):
    """Input model for creating a new beneficiary."""
    
    phone_number: str = Field(..., description="Raw phone number (will be hashed)")
    demographics: Demographics
    profiling_slots: ProfilingSlots
    consent_audit: ConsentAudit
    preferred_language: str = "hi"
    detected_dialect: Optional[str] = "bhojpuri_mixed"


class BeneficiaryUpdate(BaseModel):
    """Input model for updating beneficiary profile."""
    
    demographics: Optional[Demographics] = None
    profiling_slots: Optional[ProfilingSlots] = None
    preferred_language: Optional[str] = None
    detected_dialect: Optional[str] = None
    last_call_at: Optional[datetime] = None
    enrolled_course_qp_codes: Optional[List[str]] = None
    active_enrollment_id: Optional[str] = None