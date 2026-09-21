"""
Course repository managing NSQF courses, Atlas Vector Search ($vectorSearch),
and high-performance in-memory cosine fallback matching.
"""

import logging
import time
from typing import Any

import numpy as np
from pydantic import ValidationError
from pymongo.errors import OperationFailure, PyMongoError

from config.config import get_settings
from schemas.course import CourseDocument
from services.db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)
settings = get_settings()


class CourseRepository(BaseRepository):
    """
    Repository for NSQF courses with Atlas Vector Search and compound filtering.
    """

    @property
    def collection(self):
        return self._client.nsqf_courses

    async def search_courses(
        self,
        query_embedding: list[float],
        district_code: str,
        education_tier: int = 1,
        limit: int = 2,
        is_enterprise: bool = False,
        has_prior_experience: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Execute semantic course search with compound filtering per spec:
        - $vectorSearch on nsqf_vector_index
        - Filters: status == ACTIVE, district_availability == district_code, min_education_tier <= education_tier
        - If candidate has enterprise intent, routes to EDP / RPL programs rather than entry wage courses.
        """
        await self.ensure_connected()
        start = time.perf_counter()

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "nsqf_vector_index",
                    "path": "course_embedding",
                    "queryVector": query_embedding,
                    "numCandidates": settings.vector_search_num_candidates,
                    "limit": settings.vector_search_limit,
                    "filter": {
                        "$and": [
                            {"status": {"$eq": "ACTIVE"}},
                            {"district_availability": {"$eq": district_code}},
                            {"min_education_tier": {"$lte": education_tier}},
                        ]
                    },
                }
            },
            {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
            {"$limit": limit},
        ]

        if self._client.is_connected and self.collection is not None:
            try:
                cursor = self.collection.aggregate(pipeline)
                results = await cursor.to_list(length=limit)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                logger.info(
                    f"Atlas Vector Search returned {len(results)} courses in {elapsed_ms:.1f}ms"
                )

                if is_enterprise and results:
                    for r in results:
                        if has_prior_experience:
                            r["pathway_type"] = "RPL_CERTIFICATION_AND_BUSINESS_UPGRADE"
                        else:
                            r["pathway_type"] = "EDP_ENTREPRENEURSHIP_DEVELOPMENT"
                return results

            except OperationFailure as op_err:
                logger.warning(
                    f"Atlas $vectorSearch not supported on this MongoDB instance ({op_err}). "
                    f"Executing vector fallback matcher."
                )
                return await self._fallback_vector_search(
                    query_embedding,
                    district_code,
                    education_tier,
                    limit,
                    is_enterprise,
                    has_prior_experience,
                )
            except Exception:
                logger.exception("Error querying courses via Atlas Search")
                return await self._fallback_vector_search(
                    query_embedding,
                    district_code,
                    education_tier,
                    limit,
                    is_enterprise,
                    has_prior_experience,
                )
        else:
            return self._mock_course_results(
                district_code, is_enterprise, has_prior_experience
            )

    async def _fallback_vector_search(
        self,
        query_embedding: list[float],
        district_code: str,
        education_tier: int,
        limit: int,
        is_enterprise: bool = False,
        has_prior_experience: bool = False,
    ) -> list[dict[str, Any]]:
        """
        High-performance in-memory cosine fallback for standard MongoDB containers or offline testing.
        """
        if not self._client.is_connected or self.collection is None:
            return self._mock_course_results(
                district_code, is_enterprise, has_prior_experience
            )

        try:
            start_fallback = time.perf_counter()
            query: dict[str, Any] = {
                "status": "ACTIVE",
                "district_availability": district_code,
                "min_education_tier": {"$lte": education_tier},
            }
            cursor = self.collection.find(query)
            docs = await cursor.to_list(length=100)

            # Broaden search if district yields zero courses
            if not docs:
                cursor = self.collection.find({"status": "ACTIVE"})
                docs = await cursor.to_list(length=100)

            if not docs:
                return self._mock_course_results(
                    district_code, is_enterprise, has_prior_experience
                )

            q_vec = np.array(query_embedding, dtype=np.float32)
            norm_q = np.linalg.norm(q_vec)
            if norm_q > 0:
                q_vec = q_vec / norm_q

            scored = []
            for d in docs:
                emb = d.get("course_embedding")
                if emb:
                    c_vec = np.array(emb, dtype=np.float32)
                    norm_c = np.linalg.norm(c_vec)
                    score = (
                        float(np.dot(q_vec, c_vec) / (norm_q * norm_c))
                        if norm_c > 0
                        else 0.0
                    )
                else:
                    score = 0.5

                d_copy = dict(d)
                d_copy["score"] = round(score, 4)
                if is_enterprise:
                    d_copy["pathway_type"] = (
                        "RPL_CERTIFICATION_AND_BUSINESS_UPGRADE"
                        if has_prior_experience
                        else "EDP_ENTREPRENEURSHIP_DEVELOPMENT"
                    )
                scored.append(d_copy)

            scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            elapsed = (time.perf_counter() - start_fallback) * 1000.0
            logger.info(
                f"Fallback cosine search returned {min(len(scored), limit)} courses in {elapsed:.1f}ms"
            )
            return scored[:limit]

        except Exception:
            logger.exception("Fallback vector search failed")
            return self._mock_course_results(
                district_code, is_enterprise, has_prior_experience
            )

    def _mock_course_results(
        self,
        district_code: str,
        is_enterprise: bool = False,
        has_prior_experience: bool = False,
    ) -> list[dict[str, Any]]:
        """Mock course recommendations matching Section 5.1 and enterprise EDP/RPL routing."""
        if is_enterprise:
            if has_prior_experience:
                return [
                    {
                        "qp_code": "RPL/Q0301",
                        "course_name": "RPL Skill Certification & Artisan Upgrade",
                        "course_name_indic": "पूर्व कौशल प्रमाणन एवं कारीगर संवर्धन (RPL)",
                        "sector": "Apparel, Made-ups & Home Furnishing",
                        "nsqf_level": 4,
                        "pathway_type": "RPL_CERTIFICATION",
                        "training_center": f"{district_code} District Skill Hub",
                        "stipend": "₹1500 per month + Tool Kit Grant",
                        "score": 0.96,
                    },
                    {
                        "qp_code": "EDP/Q0002",
                        "course_name": "Micro-Enterprise Incubation & Digital Payments",
                        "course_name_indic": "सूक्ष्म उद्योग स्थापना एवं डिजिटल लेन-देन",
                        "sector": "Management & Entrepreneurship",
                        "nsqf_level": 4,
                        "pathway_type": "EDP_INCUBATION",
                        "training_center": f"{district_code} RSETI / PMKK Center",
                        "stipend": "₹1500 per month",
                        "score": 0.91,
                    },
                ]
            else:
                return [
                    {
                        "qp_code": "EDP/Q0001",
                        "course_name": "Entrepreneurship Development Program (EDP) for Artisans",
                        "course_name_indic": "कारीगर उद्यमिता विकास कार्यक्रम (EDP)",
                        "sector": "Management & Entrepreneurship",
                        "nsqf_level": 4,
                        "pathway_type": "EDP_TRAINING",
                        "training_center": f"{district_code} RSETI Center",
                        "stipend": "₹1500 per month",
                        "score": 0.95,
                    },
                    {
                        "qp_code": "AMH/Q0301",
                        "course_name": "Self Employed Tailor",
                        "course_name_indic": "स्व-रोज़गार दर्जी",
                        "sector": "Apparel, Made-ups & Home Furnishing",
                        "nsqf_level": 4,
                        "pathway_type": "SELF_EMPLOYMENT_SKILL",
                        "training_center": f"{district_code} Skill Center, Cantt",
                        "stipend": "₹1500 per month",
                        "score": 0.92,
                    },
                ]

        return [
            {
                "qp_code": "AMH/Q0301",
                "course_name": "Self Employed Tailor",
                "course_name_indic": "स्व-रोज़गार दर्जी",
                "sector": "Apparel, Made-ups & Home Furnishing",
                "nsqf_level": 4,
                "training_center": f"{district_code} Skill Center, Cantt",
                "stipend": "₹1500 per month",
                "score": 0.94,
            },
            {
                "qp_code": "AMH/Q1001",
                "course_name": "Hand Embroiderer",
                "course_name_indic": "कसीदाकारी कारीगर",
                "sector": "Apparel, Made-ups & Home Furnishing",
                "nsqf_level": 3,
                "training_center": f"{district_code} Rural ITI Center",
                "stipend": "₹1500 per month",
                "score": 0.88,
            },
        ]

    async def get_by_qp_code(self, qp_code: str) -> CourseDocument | None:
        """Fetch course by Qualification Pack code."""
        if not await self.ensure_connected() or self.collection is None:
            return None
        try:
            doc = await self.collection.find_one({"qp_code": qp_code})
            if doc:
                return CourseDocument.model_validate(doc)
            return None
        except ValidationError:
            logger.exception("Invalid course document for %s", qp_code)
            return None
        except PyMongoError:
            logger.exception("Failed to get course %s", qp_code)
            return None

    async def upsert_course(self, course: CourseDocument) -> bool:
        """Insert or update course document."""
        if not await self.ensure_connected() or self.collection is None:
            return False
        try:
            doc = course.model_dump()
            await self.collection.update_one(
                {"qp_code": course.qp_code},
                {"$set": doc},
                upsert=True,
            )
            return True
        except PyMongoError as e:
            logger.error(f"Failed to upsert course {course.qp_code}: {e}")
            return False

    async def bulk_upsert_courses(self, courses: list[CourseDocument]) -> int:
        """Bulk insert/update courses."""
        if not courses:
            return 0
        if not await self.ensure_connected() or self.collection is None:
            return 0
        count = 0
        for c in courses:
            ok = await self.upsert_course(c)
            if ok:
                count += 1
        return count
