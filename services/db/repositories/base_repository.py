"""
Base repository providing common async MongoDB operations and error handling.
"""

import logging
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorCollection

from services.db.mongo_client import MongoDBClient, get_mongo_client

logger = logging.getLogger(__name__)


class BaseRepository:
    """Abstract base repository for MongoDB collections."""

    def __init__(self, client: Optional[MongoDBClient] = None):
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
    def collection(self) -> Optional[AsyncIOMotorCollection]:
        raise NotImplementedError("Subclasses must implement collection property")

    async def count(self, filter_dict: Optional[Dict[str, Any]] = None) -> int:
        """Count documents matching filter."""
        if not await self.ensure_connected() or self.collection is None:
            return 0
        try:
            return await self.collection.count_documents(filter_dict or {})
        except Exception as e:
            logger.error(f"Failed to count documents: {e}")
            return 0
