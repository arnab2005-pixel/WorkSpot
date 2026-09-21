"""
Database indexing manager for PM-AJAY Voice Assistant.

Idempotently configures unique, compound, text, and TTL indexes across all MongoDB collections.
"""

import logging
from typing import Dict, List, Any
from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.errors import PyMongoError

from .mongo_client import MongoDBClient, get_mongo_client

logger = logging.getLogger(__name__)


async def ensure_indexes(client: MongoDBClient = None) -> Dict[str, List[str]]:
    """
    Create or verify all necessary indexes across the PM-AJAY collections.
    Returns a dictionary mapping collection name to list of confirmed index names.
    """
    client = client or get_mongo_client()
    connected = await client.connect()
    if not connected or client.db is None:
        logger.warning("MongoDB not connected. Skipping index creation.")
        return {}

    created_indexes: Dict[str, List[str]] = {}

    try:
        # ==========================================
        # 1. beneficiaries indexes
        # ==========================================
        b_col = client.beneficiaries
        b_idxs = [
            ([("phone_hash", ASCENDING)], {"unique": True, "name": "idx_phone_hash_unique"}),
            ([("demographics.district_code", ASCENDING)], {"name": "idx_district_code"}),
            ([("created_at", DESCENDING)], {"name": "idx_created_at_desc"}),
            (
                [
                    ("demographics.district_code", ASCENDING),
                    ("profiling_slots.employment_intent", ASCENDING),
                ],
                {"name": "idx_district_intent_compound"},
            ),
        ]
        created_indexes["beneficiaries"] = []
        for keys, kwargs in b_idxs:
            try:
                name = await b_col.create_index(keys, **kwargs)
                created_indexes["beneficiaries"].append(name)
            except PyMongoError as e:
                logger.debug(f"Index {kwargs.get('name')} notice on beneficiaries: {e}")

        # ==========================================
        # 2. nsqf_courses indexes
        # ==========================================
        c_col = client.nsqf_courses
        c_idxs = [
            ([("qp_code", ASCENDING)], {"unique": True, "name": "idx_qp_code_unique"}),
            (
                [
                    ("district_availability", ASCENDING),
                    ("status", ASCENDING),
                    ("min_education_tier", ASCENDING),
                ],
                {"name": "idx_course_filter_compound"},
            ),
            (
                [
                    ("course_name_indic", TEXT),
                    ("course_name", TEXT),
                    ("sector", TEXT),
                    ("target_occupations", TEXT),
                ],
                {"name": "idx_course_text_search", "default_language": "none"},
            ),
        ]
        created_indexes["nsqf_courses"] = []
        for keys, kwargs in c_idxs:
            try:
                name = await c_col.create_index(keys, **kwargs)
                created_indexes["nsqf_courses"].append(name)
            except PyMongoError as e:
                logger.debug(f"Index {kwargs.get('name')} notice on nsqf_courses: {e}")

        # ==========================================
        # 3. call_sessions indexes
        # ==========================================
        s_col = client.call_sessions
        s_idxs = [
            ([("session_id", ASCENDING)], {"unique": True, "name": "idx_session_id_unique"}),
            ([("phone_hash", ASCENDING), ("start_time", DESCENDING)], {"name": "idx_phone_history_compound"}),
            ([("start_time", ASCENDING)], {"expireAfterSeconds": 7776000, "name": "idx_ttl_90_days"}),  # 90 days
        ]
        created_indexes["call_sessions"] = []
        for keys, kwargs in s_idxs:
            try:
                name = await s_col.create_index(keys, **kwargs)
                created_indexes["call_sessions"].append(name)
            except PyMongoError as e:
                logger.debug(f"Index {kwargs.get('name')} notice on call_sessions: {e}")

        # ==========================================
        # 4. lgd_districts indexes
        # ==========================================
        d_col = client.lgd_districts
        d_idxs = [
            ([("district_code", ASCENDING)], {"unique": True, "name": "idx_lgd_district_code"}),
            ([("aliases", ASCENDING)], {"name": "idx_lgd_aliases"}),
        ]
        created_indexes["lgd_districts"] = []
        for keys, kwargs in d_idxs:
            try:
                name = await d_col.create_index(keys, **kwargs)
                created_indexes["lgd_districts"].append(name)
            except PyMongoError as e:
                logger.debug(f"Index {kwargs.get('name')} notice on lgd_districts: {e}")

        # ==========================================
        # 5. dpiu_applications indexes
        # ==========================================
        app_col = client.dpiu_applications
        app_idxs = [
            ([("application_id", ASCENDING)], {"unique": True, "name": "idx_dpiu_app_id"}),
            ([("district_code", ASCENDING), ("status", ASCENDING)], {"name": "idx_dpiu_district_status"}),
        ]
        created_indexes["dpiu_applications"] = []
        for keys, kwargs in app_idxs:
            try:
                name = await app_col.create_index(keys, **kwargs)
                created_indexes["dpiu_applications"].append(name)
            except PyMongoError as e:
                logger.debug(f"Index {kwargs.get('name')} notice on dpiu_applications: {e}")

        logger.info(f"Database indexes verified across {len(created_indexes)} collections.")
        return created_indexes

    except Exception as exc:
        logger.exception("Error ensuring MongoDB indexes: %s", exc)
        return created_indexes
