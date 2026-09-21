"""
MongoDB Service for NSQF courses and beneficiary records.

Executes Atlas Vector Search ($vectorSearch) with compound filtering:
- Status: ACTIVE
- District availability: matching district_code
- Education requirement: min_education_tier <= beneficiary tier
Includes fallback cosine-similarity matcher for standalone/offline MongoDB testing.
"""

import logging
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

from config.config import get_settings
from schemas.course import CourseDocument
from schemas.beneficiary import BeneficiaryRecord
from schemas.beneficiary_profile import EnterpriseAspirations

logger = logging.getLogger(__name__)
settings = get_settings()


class MongoService:
    """
    MongoDB service managing beneficiaries and NSQF courses with Atlas Vector Search.
    """

    def __init__(
        self,
        mongo_url: Optional[str] = None,
        database_name: Optional[str] = None,
    ):
        self.mongo_url = mongo_url or settings.mongodb_url
        self.database_name = database_name or settings.mongodb_database
        self.client: Optional[AsyncIOMotorClient] = None
        self.db = None
        self._connected = False

    async def connect(self):
        """Establish connection to MongoDB."""
        if self._connected and self.db is not None:
            return
        try:
            self.client = AsyncIOMotorClient(
                self.mongo_url,
                maxPoolSize=settings.mongodb_max_pool_size,
                serverSelectionTimeoutMS=2000,
            )
            self.db = self.client[self.database_name]
            # Verify connectivity
            await self.client.admin.command("ping")
            self._connected = True
            logger.info(f"Connected to MongoDB at {self.mongo_url}/{self.database_name}")
        except Exception as e:
            logger.warning(f"MongoDB connection failed: {e}. Running in disconnected/mock mode.")
            self._connected = False

    async def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("MongoDB connection closed.")

    async def search_courses(
        self,
        query_embedding: List[float],
        district_code: str,
        education_tier: int = 1,
        limit: int = 2,
        is_enterprise: bool = False,
        has_prior_experience: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Execute Atlas Vector Search query with compound filtering per spec:
        - $vectorSearch on nsqf_vector_index
        - Filter: status == ACTIVE, district_availability == district_code, min_education_tier <= education_tier
        - If candidate has enterprise intent, routes to EDP / RPL programs rather than entry wage courses.
        """
        await self.connect()
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
            {
                "$addFields": {
                    "score": {"$meta": "vectorSearchScore"}
                }
            },
            {"$limit": limit},
        ]

        if self._connected and self.db is not None:
            try:
                cursor = self.db.nsqf_courses.aggregate(pipeline)
                results = await cursor.to_list(length=limit)
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                logger.info(f"Atlas Vector Search returned {len(results)} courses in {elapsed_ms:.1f}ms")
                if is_enterprise and results:
                    # Tag with EDP/RPL pathway
                    for r in results:
                        if has_prior_experience:
                            r["pathway_type"] = "RPL_CERTIFICATION_AND_BUSINESS_UPGRADE"
                        else:
                            r["pathway_type"] = "EDP_ENTREPRENEURSHIP_DEVELOPMENT"
                return results
            except OperationFailure as op_err:
                logger.warning(
                    f"Atlas $vectorSearch not supported on local Mongo ({op_err}). Running in-memory cosine fallback."
                )
                return await self._fallback_vector_search(
                    query_embedding, district_code, education_tier, limit, is_enterprise, has_prior_experience
                )
            except Exception as e:
                logger.error(f"Error querying courses: {e}", exc_info=True)
                return await self._fallback_vector_search(
                    query_embedding, district_code, education_tier, limit, is_enterprise, has_prior_experience
                )
        else:
            return self._mock_course_results(district_code, is_enterprise, has_prior_experience)

    async def _fallback_vector_search(
        self,
        query_embedding: List[float],
        district_code: str,
        education_tier: int,
        limit: int,
        is_enterprise: bool = False,
        has_prior_experience: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fallback search for standard MongoDB or testing without Atlas Search engine.
        """
        if not self._connected or self.db is None:
            return self._mock_course_results(district_code, is_enterprise, has_prior_experience)

        try:
            dist_clean = district_code.replace("UP_", "").replace("BR_", "").replace("MP_", "").replace("RJ_", "").replace("MH_", "").replace("WB_", "").strip()
            query = {
                "status": "ACTIVE",
                "$or": [
                    {"district_availability": district_code},
                    {"district_availability": {"$regex": dist_clean, "$options": "i"}},
                ],
                "min_education_tier": {"$lte": education_tier},
            }
            cursor = self.db.nsqf_courses.find(query)
            docs = await cursor.to_list(length=100)

            if not docs:
                cursor = self.db.nsqf_courses.find({"status": "ACTIVE"})
                docs = await cursor.to_list(length=100)

            if not docs:
                return self._mock_course_results(district_code, is_enterprise, has_prior_experience)

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
                    score = float(np.dot(q_vec, c_vec) / (norm_q * norm_c)) if norm_c > 0 else 0.0
                else:
                    score = 0.5
                d_copy = dict(d)
                d_copy["score"] = score
                if is_enterprise:
                    d_copy["pathway_type"] = (
                        "RPL_CERTIFICATION_AND_BUSINESS_UPGRADE"
                        if has_prior_experience
                        else "EDP_ENTREPRENEURSHIP_DEVELOPMENT"
                    )
                scored.append(d_copy)

            scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)
            return scored[:limit]

        except Exception as e:
            logger.error(f"Fallback vector search failed: {e}")
            return self._mock_course_results(district_code, is_enterprise, has_prior_experience)

    def _mock_course_results(
        self,
        district_code: str,
        is_enterprise: bool = False,
        has_prior_experience: bool = False,
    ) -> List[Dict[str, Any]]:
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

    async def process_enterprise_routing(
        self,
        phone_hash: str,
        enterprise: EnterpriseAspirations,
    ) -> Dict[str, Any]:
        """
        Process enterprise aspirations and apply financial scheme alignment:
        1. Capital Subsidy Prefill: If estimated_capital_required_inr == 'MICRO_UNDER_50K',
           flags candidate with eligible_for_gia_asset_grant = True and pushes prefill to DPIU.
        2. Credit Desk Routing: If 'SMALL_50K_TO_2LAKH', auto-routes to NSFDC Micro-Credit Desk.
        3. Mudra / Term Loan: If 'MEDIUM_2LAKH_TO_5LAKH', auto-routes to Mudra Kishore.
        """
        await self.connect()

        capital_range = enterprise.estimated_capital_required_inr
        is_gia_eligible = False
        credit_routing = None
        dpiu_status = None

        if capital_range == "MICRO_UNDER_50K":
            is_gia_eligible = True
            credit_routing = "PM_AJAY_CAPITAL_SUBSIDY"
            dpiu_status = "PREFILL_DISPATCHED_TO_DPIU"
        elif capital_range == "SMALL_50K_TO_2LAKH":
            is_gia_eligible = False
            credit_routing = "NSFDC_MICRO_CREDIT"
            dpiu_status = "ROUTED_TO_NSFDC_DESK"
        elif capital_range == "MEDIUM_2LAKH_TO_5LAKH":
            is_gia_eligible = False
            credit_routing = "MUDRA_KISHORE"
            dpiu_status = "ROUTED_TO_MUDRA_PORTAL"
        else:
            is_gia_eligible = True
            credit_routing = "PM_AJAY_CAPITAL_SUBSIDY"
            dpiu_status = "PENDING_CAPITAL_ASSESSMENT"

        routing_record = {
            "eligible_for_gia_asset_grant": is_gia_eligible,
            "credit_desk_routing": credit_routing,
            "dpiu_prefill_status": dpiu_status,
            "enterprise_details": enterprise.model_dump(),
        }

        if self._connected and self.db is not None and phone_hash:
            try:
                await self.db.beneficiaries.update_one(
                    {"phone_hash": phone_hash},
                    {"$set": routing_record},
                    upsert=True,
                )
                logger.info(f"Updated beneficiary {phone_hash[:8]}... with GIA/credit routing: {credit_routing}")
            except Exception as e:
                logger.error(f"Failed to update beneficiary enterprise routing: {e}")

        return routing_record

    async def save_beneficiary(self, beneficiary: BeneficiaryRecord) -> bool:
        """Upsert a beneficiary record."""
        await self.connect()
        if not self._connected or self.db is None:
            return True

        try:
            doc = beneficiary.model_dump()
            await self.db.beneficiaries.update_one(
                {"phone_hash": beneficiary.phone_hash},
                {"$set": doc},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save beneficiary: {e}")
            return False

    async def get_beneficiary(self, phone_hash: str) -> Optional[BeneficiaryRecord]:
        """Retrieve a beneficiary by salted phone hash."""
        await self.connect()
        if not self._connected or self.db is None:
            return None

        try:
            data = await self.db.beneficiaries.find_one({"phone_hash": phone_hash})
            if data:
                return BeneficiaryRecord.model_validate(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get beneficiary: {e}")
            return None

    async def save_session_record(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Persist or update conversational session document in MongoDB."""
        await self.connect()
        if not self._connected or self.db is None:
            return False

        try:
            data["session_id"] = session_id
            data["updated_at"] = datetime.now(timezone.utc)
            await self.db.sessions.update_one(
                {"session_id": session_id},
                {"$set": data},
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save session to MongoDB: {e}")
            return False

    async def get_session_record(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve conversational session document from MongoDB."""
        await self.connect()
        if not self._connected or self.db is None:
            return None

        try:
            return await self.db.sessions.find_one({"session_id": session_id})
        except Exception as e:
            logger.error(f"Failed to get session from MongoDB: {e}")
            return None

