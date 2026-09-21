"""
Asynchronous MongoDB connection manager for PM-AJAY Voice Assistant.

Handles connection pooling, Atlas Vector Search capability detection,
health monitoring, and graceful resource teardown.
"""

import logging
import time
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError

from config.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MongoDBClient:
    """
    Async MongoDB connection manager utilizing Motor.
    """

    def __init__(
        self,
        mongo_url: str | None = None,
        database_name: str | None = None,
        max_pool_size: int | None = None,
    ):
        self.mongo_url = mongo_url or settings.mongodb_url
        self.database_name = database_name or settings.mongodb_database
        self.max_pool_size = max_pool_size or settings.mongodb_max_pool_size
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None
        self._connected: bool = False
        self._is_atlas_search_supported: bool | None = None

    @property
    def client(self) -> AsyncIOMotorClient | None:
        return self._client

    @property
    def db(self) -> AsyncIOMotorDatabase | None:
        return self._db

    @property
    def is_connected(self) -> bool:
        return self._connected and self._db is not None

    async def connect(self) -> bool:
        """
        Establish connection to MongoDB with connection pooling and ping verification.
        """
        if self._connected and self._db is not None:
            return True

        try:
            self._client = AsyncIOMotorClient(
                self.mongo_url,
                maxPoolSize=self.max_pool_size,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000,
                socketTimeoutMS=5000,
            )
            self._db = self._client[self.database_name]

            # Verify connectivity via ping command
            start_ping = time.perf_counter()
            await self._client.admin.command("ping")
            ping_ms = (time.perf_counter() - start_ping) * 1000.0

            self._connected = True
            logger.info(
                f"Connected to MongoDB at {self.mongo_url}/{self.database_name} "
                f"(ping: {ping_ms:.1f}ms, pool: {self.max_pool_size})"
            )
            return True
        except (ConnectionFailure, ServerSelectionTimeoutError) as conn_err:
            logger.warning(
                f"MongoDB connection failed ({conn_err}). "
                f"Operating in disconnected / in-memory fallback mode."
            )
            self._connected = False
            return False
        except Exception:
            logger.exception("Unexpected MongoDB connection error")
            self._connected = False
            return False

    async def ping(self) -> dict[str, Any]:
        """
        Healthcheck probe returning connectivity status and round-trip latency.
        """
        if not self._connected or not self._client:
            connected = await self.connect()
            if not connected:
                return {"status": "unhealthy", "connected": False, "latency_ms": -1}

        try:
            start = time.perf_counter()
            await self._client.admin.command("ping")
            latency_ms = (time.perf_counter() - start) * 1000.0
            return {
                "status": "healthy",
                "connected": True,
                "latency_ms": round(latency_ms, 2),
                "database": self.database_name,
            }
        except PyMongoError as exc:
            logger.warning("MongoDB ping failed: %s", exc)
            return {"status": "unhealthy", "connected": False, "error": str(exc)}

    async def check_atlas_vector_support(self) -> bool:
        """
        Probe whether native Atlas $vectorSearch is supported on this MongoDB deployment.
        Community MongoDB standalone returns OperationFailure for $vectorSearch.
        """
        if self._is_atlas_search_supported is not None:
            return self._is_atlas_search_supported

        if not self.is_connected:
            await self.connect()
            if not self.is_connected:
                self._is_atlas_search_supported = False
                return False

        try:
            # Run dry aggregate pipeline with empty query to test $vectorSearch support
            test_pipeline = [
                {
                    "$vectorSearch": {
                        "index": "nsqf_vector_index",
                        "path": "course_embedding",
                        "queryVector": [0.0] * 768,
                        "numCandidates": 1,
                        "limit": 1,
                    }
                }
            ]
            cursor = self.db.nsqf_courses.aggregate(test_pipeline)
            await cursor.to_list(length=1)
            self._is_atlas_search_supported = True
            logger.info("MongoDB Atlas $vectorSearch confirmed active and operational.")
        except PyMongoError as exc:
            logger.info(
                "MongoDB deployment does not support Atlas $vectorSearch (%s). "
                "Using accelerated in-memory vector matcher.",
                exc,
            )
            self._is_atlas_search_supported = False

        return self._is_atlas_search_supported

    async def close(self):
        """Close client connection pool and release resources."""
        if self._client:
            self._client.close()
            self._connected = False
            self._client = None
            self._db = None
            self._is_atlas_search_supported = None
            logger.info("MongoDB client connections closed.")

    # Collection accessors
    @property
    def beneficiaries(self):
        return self._db.beneficiaries if self._db is not None else None

    @property
    def nsqf_courses(self):
        return self._db.nsqf_courses if self._db is not None else None

    @property
    def call_sessions(self):
        return self._db.call_sessions if self._db is not None else None

    @property
    def lgd_districts(self):
        return self._db.lgd_districts if self._db is not None else None

    @property
    def dpiu_applications(self):
        return self._db.dpiu_applications if self._db is not None else None


_mongo_client_instance: MongoDBClient | None = None


def get_mongo_client() -> MongoDBClient:
    """Singleton getter for MongoDBClient."""
    global _mongo_client_instance
    if _mongo_client_instance is None:
        _mongo_client_instance = MongoDBClient()
    return _mongo_client_instance
