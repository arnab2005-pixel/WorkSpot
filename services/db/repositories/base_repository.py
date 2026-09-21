"""
Base repository providing common async MongoDB operations and error handling.
"""

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo.errors import PyMongoError

from services.db.mongo_client import MongoDBClient, get_mongo_client

logger = logging.getLogger(__name__)


class BaseRepository:
    """Abstract base repository for MongoDB collections."""

    def __init__(self, client: MongoDBClient | None = None):
        self._client = client or get_mongo_client()

    @property
    def client(self) -> MongoDBClient:
        return self._client

    async def ensure_connected(self) -> bool:
        """Ensure connection is ready before executing queries."""
        if not self._client.is_connected:
            return await self._client.connect()
        return True

    @property
    def collection(self) -> AsyncIOMotorCollection | None:
        raise NotImplementedError("Subclasses must implement collection property")

    async def count(self, filter_dict: dict[str, Any] | None = None) -> int:
        """Count documents matching filter."""
        if not await self.ensure_connected() or self.collection is None:
            return 0
        try:
            return await self.collection.count_documents(filter_dict or {})
        except PyMongoError:
            logger.exception("Failed to count documents")
            return 0
