"""
Unit tests for MongoDB Atlas Vector Search integration and course schemas.
"""

import pytest
from datetime import datetime, timezone
from schemas.course import CourseDocument
from schemas.beneficiary import BeneficiaryRecord, Demographics, ProfilingSlots, ConsentAudit
from services.recommendation.embedder import CourseEmbedder
from services.recommendation.mongo_service import MongoService


def test_course_document_schema_validation():
    """Verify CourseDocument conforms to Section 3.2 schema."""
    dummy_embedding = [0.1] * 768
    course = CourseDocument(
        qp_code="AMH/Q0301",
        course_name="Self Employed Tailor",
        course_name_indic="स्व-रोज़गार दर्जी",
        sector="Apparel",
        nsqf_level=4,
        min_education_tier=1,
        is_residential=False,
        district_availability=["UP_VARANASI"],
        course_embedding=dummy_embedding,
        status="ACTIVE",
    )
    assert course.qp_code == "AMH/Q0301"
    assert len(course.course_embedding) == 768


def test_beneficiary_record_schema_validation():
    """Verify BeneficiaryRecord conforms to Section 3.1 schema."""
    beneficiary = BeneficiaryRecord(
        phone_hash="a" * 64,
        preferred_language="hi",
        detected_dialect="bhojpuri_mixed",
        demographics=Demographics(
            district_code="UP_VARANASI",
            block_name="Chiraigaon",
            education_level="class_8",
        ),
        profiling_slots=ProfilingSlots(
            traditional_trade="सिलाई / Tailoring",
            mobility_radius_km=15,
            employment_intent="SELF_EMPLOYMENT",
            prior_experience=False,
        ),
        consent_audit=ConsentAudit(
            voice_verified=True,
            consent_timestamp=datetime.now(timezone.utc),
            audio_vault_ref="s3://pm-ajay-vault/consent_123.wav",
        ),
    )
    assert beneficiary.demographics.district_code == "UP_VARANASI"
    assert beneficiary.profiling_slots.employment_intent == "SELF_EMPLOYMENT"


@pytest.mark.asyncio
async def test_vector_search_pipeline_fallback():
    """Verify vector search returns top recommendations matching district."""
    embedder = CourseEmbedder()
    mongo = MongoService()

    query_vec = embedder.embed_text("सिलाई दर्जी")
    assert len(query_vec) == 768

    results = await mongo.search_courses(
        query_embedding=query_vec,
        district_code="UP_VARANASI",
        education_tier=1,
        limit=2,
    )

    assert len(results) == 2
    assert "qp_code" in results[0]
    assert "course_name" in results[0]
