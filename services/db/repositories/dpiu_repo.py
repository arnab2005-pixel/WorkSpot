"""
DPIU repository managing pre-filled PM-AJAY capital subsidy applications and scheme routing.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from pymongo.errors import PyMongoError

from schemas.dpiu_application import DpiuApplicationRecord
from services.db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DpiuRepository(BaseRepository):
    """
    Repository for pre-filled applications submitted to District Project Implementation Units.
    """

    @property
    def collection(self):
        return self._client.dpiu_applications

    async def create_application(self, app: DpiuApplicationRecord) -> bool:
        """Insert or update a DPIU application pre-fill."""
        if not await self.ensure_connected() or self.collection is None:
            return True
        try:
            doc = app.model_dump()
            doc["updated_at"] = datetime.now(timezone.utc)
            await self.collection.update_one(
                {"application_id": app.application_id},
                {"$set": doc},
                upsert=True,
            )
            logger.info(f"DPIU application created/updated: {app.application_id}")
            return True
        except PyMongoError as e:
            logger.error(f"Failed to create DPIU application {app.application_id}: {e}")
            return False

    async def get_application(
        self, application_id: str
    ) -> DpiuApplicationRecord | None:
        """Retrieve DPIU application by ID."""
        if not await self.ensure_connected() or self.collection is None:
            return None
        try:
            doc = await self.collection.find_one({"application_id": application_id})
            if doc:
                return DpiuApplicationRecord.model_validate(doc)
            return None
        except ValidationError:
            logger.exception("Invalid DPIU application document for %s", application_id)
            return None
        except PyMongoError:
            logger.exception("Failed to get DPIU application %s", application_id)
            return None

    async def list_by_district(
        self,
        district_code: str,
        status: str | None = None,
        limit: int = 50,
    ) -> list[DpiuApplicationRecord]:
        """List applications by district and optional status filter."""
        if not await self.ensure_connected() or self.collection is None:
            return []
        query: dict[str, Any] = {"district_code": district_code}
        if status:
            query["status"] = status
        try:
            cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [DpiuApplicationRecord.model_validate(d) for d in docs]
        except ValidationError:
            logger.exception(
                "Invalid DPIU application document in district %s", district_code
            )
            return []
        except PyMongoError:
            logger.exception("Failed to list DPIU applications for %s", district_code)
            return []

    async def update_status(self, application_id: str, new_status: str) -> bool:
        """Update processing status of an application."""
        if not await self.ensure_connected() or self.collection is None:
            return False
        try:
            await self.collection.update_one(
                {"application_id": application_id},
                {
                    "$set": {
                        "status": new_status,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            return True
        except PyMongoError as e:
            logger.error(f"Failed to update status for {application_id}: {e}")
            return False
