"""
District repository managing LGD master directories and dialect alias resolution.
"""

import logging
from typing import Optional, List, Dict, Any
from pymongo.errors import PyMongoError

from schemas.lgd_district import LgdDistrictRecord
from services.db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DistrictRepository(BaseRepository):
    """
    Repository for LGD districts with phonetic and colloquial alias mapping.
    """

    @property
    def collection(self):
        return self._client.lgd_districts

    async def resolve_district(self, text: str) -> Optional[LgdDistrictRecord]:
        """
        Resolve spoken text (English/Hindi/Dialect) to standardized LGD district record.
        e.g. "बनारस", "Kashi", "Varanasi" -> "UP_VARANASI".
        """
        if not text or not await self.ensure_connected() or self.collection is None:
            return None

        clean_text = text.strip()

        try:
            # 1. Direct code or name match
            doc = await self.collection.find_one(
                {
                    "$or": [
                        {"district_code": clean_text.upper()},
                        {"district_name_en": {"$regex": f"^{clean_text}$", "$options": "i"}},
                        {"district_name_hi": clean_text},
                        {"aliases": {"$in": [clean_text, clean_text.lower(), clean_text.title()]}},
                    ]
                }
            )
            if doc:
                return LgdDistrictRecord.model_validate(doc)

            # 2. Substring match inside spoken sentence
            # (e.g. "हम बनारस के रहे वाला हईं" contains "बनारस")
            all_districts = await self.list_districts()
            for d in all_districts:
                if d.district_name_hi in clean_text or d.district_name_en.lower() in clean_text.lower():
                    return d
                for alias in d.aliases:
                    if alias in clean_text or alias.lower() in clean_text.lower():
                        return d

            return None
        except Exception as e:
            logger.error(f"Failed to resolve district from text '{text}': {e}")
            return None

    async def get_by_code(self, district_code: str) -> Optional[LgdDistrictRecord]:
        """Fetch district by LGD code."""
        if not await self.ensure_connected() or self.collection is None:
            return None
        try:
            doc = await self.collection.find_one({"district_code": district_code})
            if doc:
                return LgdDistrictRecord.model_validate(doc)
            return None
        except Exception as e:
            logger.error(f"Failed to get district {district_code}: {e}")
            return None

    async def upsert_district(self, district: LgdDistrictRecord) -> bool:
        """Upsert an LGD district record."""
        if not await self.ensure_connected() or self.collection is None:
            return False
        try:
            await self.collection.update_one(
                {"district_code": district.district_code},
                {"$set": district.model_dump()},
                upsert=True,
            )
            return True
        except PyMongoError as e:
            logger.error(f"Failed to upsert district {district.district_code}: {e}")
            return False

    async def list_districts(self, state_code: Optional[str] = None) -> List[LgdDistrictRecord]:
        """List all districts, optionally filtered by state."""
        if not await self.ensure_connected() or self.collection is None:
            return []
        query = {"state_code": state_code} if state_code else {}
        try:
            cursor = self.collection.find(query)
            docs = await cursor.to_list(length=200)
            return [LgdDistrictRecord.model_validate(d) for d in docs]
        except Exception as e:
            logger.error(f"Failed to list districts: {e}")
            return []
