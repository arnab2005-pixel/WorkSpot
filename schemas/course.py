"""
Course data models for PM-AJAY Voice Assistant.

These models represent NSQF courses stored in MongoDB with vector embeddings
for semantic search via Atlas Vector Search.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CourseDocument(BaseModel):
    """
    NSQF Course document stored in MongoDB with vector embedding.

    This is the primary document for the `nsqf_courses` collection.
    The `course_embedding` field is indexed for Atlas Vector Search.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "qp_code": "AMH/Q0301",
                "course_name": "Self Employed Tailor",
                "course_name_indic": "स्व-रोज़गार दर्जी",
                "sector": "Apparel, Made-ups & Home Furnishing",
                "nsqf_level": 4,
                "min_education_tier": 1,
                "is_residential": False,
                "district_availability": ["UP_VARANASI", "UP_PRAYAGRAJ", "BR_PATNA"],
                "course_embedding": [0.1, 0.2, ...],  # 768-dim vector
                "status": "ACTIVE",
                "duration_hours": 360,
                "stipend_per_month": 1500,
                "training_partners": ["Varanasi Skill Center", "Cantt ITI"],
            }
        },
    )

    # Primary identifier
    qp_code: str = Field(
        ...,
        description="Qualification Pack Code (e.g., 'AMH/Q0301', 'CSC/Q0101')",
        min_length=5,
        max_length=20,
    )

    # Course details
    course_name: str = Field(
        ..., description="Official course name in English", max_length=200
    )
    course_name_indic: str = Field(
        ..., description="Course name in Hindi/Devanagari", max_length=200
    )
    sector: str = Field(
        ..., description="Sector Skill Council sector name", max_length=100
    )
    nsqf_level: int = Field(..., description="NSQF Level (1-8)", ge=1, le=8)
    min_education_tier: int = Field(
        ...,
        description="Minimum education requirement: 0=None, 1=Class 5, 2=Class 8, 3=Class 10, 4=Class 12",
        ge=0,
        le=4,
    )

    # Logistics
    is_residential: bool = Field(
        default=False, description="Whether course requires residential stay"
    )
    district_availability: list[str] = Field(
        ...,
        description="List of LGD district codes where course is available",
        min_length=1,
    )
    duration_hours: int = Field(
        default=300, description="Total course duration in hours", ge=40, le=2000
    )

    # Financial
    stipend_per_month: int = Field(
        default=0, description="Monthly stipend in INR (NSFDC/PM-AJAY)", ge=0
    )
    course_fee: int = Field(default=0, description="Course fee in INR (if any)", ge=0)

    # Vector embedding for semantic search (768-dim from BGE-M3 or Indic-BERT)
    course_embedding: list[float] = Field(
        ..., description="768-dim dense embedding vector"
    )

    # Status and metadata
    status: Literal["ACTIVE", "INACTIVE", "ARCHIVED"] = Field(
        default="ACTIVE", description="Course availability status"
    )
    training_partners: list[str] = Field(
        default_factory=list,
        description="Names of training centers/partners offering this course",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Additional metadata for filtering
    gender_preference: Literal["ANY", "MALE", "FEMALE", "TRANSGENDER"] | None = Field(
        default="ANY", description="Gender preference for the course"
    )
    age_min: int = Field(default=18, ge=14, le=60)
    age_max: int = Field(default=45, ge=18, le=60)
    disability_friendly: bool = Field(default=False)
    sc_st_reserved_seats: int = Field(default=0, ge=0)


class CourseCreate(BaseModel):
    """Input model for creating a new course (without embedding - generated server-side)."""

    qp_code: str = Field(..., min_length=5, max_length=20)
    course_name: str = Field(..., max_length=200)
    course_name_indic: str = Field(..., max_length=200)
    sector: str = Field(..., max_length=100)
    nsqf_level: int = Field(..., ge=1, le=8)
    min_education_tier: int = Field(..., ge=0, le=4)
    is_residential: bool = False
    district_availability: list[str] = Field(..., min_length=1)
    duration_hours: int = Field(default=300, ge=40, le=2000)
    stipend_per_month: int = Field(default=0, ge=0)
    course_fee: int = Field(default=0, ge=0)
    training_partners: list[str] = Field(default_factory=list)
    gender_preference: Literal["ANY", "MALE", "FEMALE", "TRANSGENDER"] = "ANY"
    age_min: int = Field(default=18, ge=14, le=60)
    age_max: int = Field(default=45, ge=18, le=60)
    disability_friendly: bool = False
    sc_st_reserved_seats: int = Field(default=0, ge=0)


class CourseSearchQuery(BaseModel):
    """Query parameters for course search."""

    query_text: str = Field(
        ..., description="Natural language query for semantic search"
    )
    district_code: str = Field(..., description="LGD district code for filtering")
    education_tier: int = Field(
        ..., ge=0, le=4, description="Beneficiary's education tier"
    )
    age: int | None = Field(None, ge=14, le=60)
    gender: Literal["MALE", "FEMALE", "TRANSGENDER"] | None = None
    employment_intent: Literal["WAGE", "SELF_EMPLOYMENT", "HYBRID"] | None = None
    mobility_radius_km: int | None = Field(None, ge=0, le=100)
    preferred_sector: str | None = None
    limit: int = Field(default=2, ge=1, le=10)


class CourseRecommendation(BaseModel):
    """Course recommendation result for frontend/API response."""

    qp_code: str
    course_name: str
    course_name_indic: str
    sector: str
    nsqf_level: int
    training_center: str
    district: str
    stipend_per_month: int
    duration_hours: int
    is_residential: bool
    match_score: float = Field(
        ..., ge=0.0, le=1.0, description="Vector similarity score"
    )
    match_reason: str = Field(
        ..., description="Human-readable reason for recommendation"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "qp_code": "AMH/Q0301",
                "course_name": "Self Employed Tailor",
                "course_name_indic": "स्व-रोज़गार दर्जी",
                "sector": "Apparel, Made-ups & Home Furnishing",
                "nsqf_level": 4,
                "training_center": "Varanasi Skill Center, Cantt",
                "district": "Varanasi",
                "stipend_per_month": 1500,
                "duration_hours": 360,
                "is_residential": False,
                "match_score": 0.92,
                "match_reason": "Matches your tailoring interest and Class 8 education. Available in Varanasi within 15km.",
            }
        }
    )


# Education tier mapping for reference
EDUCATION_TIER_MAP = {
    "none": 0,
    "class_5": 1,
    "class_8": 2,
    "class_10": 3,
    "class_12": 4,
    "graduate": 4,
    "post_graduate": 4,
}

EDUCATION_TIER_LABELS = {
    0: "निरक्षर / No formal education",
    1: "कक्षा 5 तक / Up to Class 5",
    2: "कक्षा 8 तक / Up to Class 8",
    3: "कक्षा 10 तक / Up to Class 10",
    4: "कक्षा 12 या ऊपर / Class 12 and above",
}
