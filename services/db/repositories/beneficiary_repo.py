"""
Beneficiary repository managing citizen profiles, DPDP Act voice consent audits,
salted phone hashing, and PM-AJAY GIA subsidy routing.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from pymongo.errors import PyMongoError

from schemas.beneficiary import BeneficiaryRecord, ConsentAudit
from schemas.beneficiary_profile import EnterpriseAspirations
from services.db.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class BeneficiaryRepository(BaseRepository):
    """
    Repository for citizen profiles with strict privacy hashing and DPDP compliance.
    """

    @property
    def collection(self):
        return self._client.beneficiaries

    @staticmethod
    def hash_phone(phone_number: str, salt: str | None = None) -> tuple[str, str]:
        """
        Produce a salted SHA-256 hash of a normalized Indian mobile number.
        Returns: (hash_hex, salt_hex)
        """
        if salt is None:
            salt = secrets.token_hex(32)

        # Normalize number
        digits = "".join(filter(str.isdigit, phone_number))
        if digits.startswith("91") and len(digits) == 12:
            normalized = "+91" + digits[2:]
        elif len(digits) == 10:
            normalized = "+91" + digits
        else:
            normalized = "+91" + digits[-10:] if len(digits) >= 10 else phone_number

        h = hashlib.sha256()
        h.update(salt.encode("utf-8"))
        h.update(normalized.encode("utf-8"))
        return h.hexdigest(), salt

    @staticmethod
    def verify_phone(phone_number: str, phone_hash: str, salt: str) -> bool:
        """Verify phone number against stored salted hash."""
        computed, _ = BeneficiaryRepository.hash_phone(phone_number, salt)
        return computed == phone_hash

    async def save_beneficiary(self, beneficiary: BeneficiaryRecord) -> bool:
        """Upsert a beneficiary record."""
        if not await self.ensure_connected() or self.collection is None:
            return True

        try:
            doc = beneficiary.model_dump()
            doc["updated_at"] = datetime.now(timezone.utc)
            await self.collection.update_one(
                {"phone_hash": beneficiary.phone_hash},
                {"$set": doc},
                upsert=True,
            )
            logger.info(f"Beneficiary profile saved: {beneficiary.phone_hash[:8]}...")
            return True
        except PyMongoError as e:
            logger.error(
                f"Failed to save beneficiary {beneficiary.phone_hash[:8]}: {e}"
            )
            return False

    async def get_beneficiary(self, phone_hash: str) -> BeneficiaryRecord | None:
        """Retrieve a beneficiary by phone hash."""
        if not await self.ensure_connected() or self.collection is None:
            return None

        try:
            doc = await self.collection.find_one({"phone_hash": phone_hash})
            if doc:
                return BeneficiaryRecord.model_validate(doc)
            return None
        except ValidationError:
            logger.exception("Invalid beneficiary document for %s", phone_hash)
            return None
        except PyMongoError:
            logger.exception("Failed to fetch beneficiary %s", phone_hash)
            return None

    async def record_voice_consent(
        self,
        phone_hash: str,
        audio_vault_ref: str,
        language: str = "hi",
        consent_timestamp: datetime | None = None,
    ) -> bool:
        """Record DPDP Act 2023 compliant voice-verified consent audit."""
        if not await self.ensure_connected() or self.collection is None:
            return False

        consent_audit = ConsentAudit(
            voice_verified=True,
            consent_timestamp=consent_timestamp or datetime.now(timezone.utc),
            audio_vault_ref=audio_vault_ref,
            language=language,
            purpose="PM-AJAY Vocational Discovery & Livelihood Scheme Matching",
            consent_withdrawn=False,
            withdrawal_timestamp=None,
        )

        try:
            await self.collection.update_one(
                {"phone_hash": phone_hash},
                {
                    "$set": {
                        "consent_audit": consent_audit.model_dump(),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
            return True
        except PyMongoError as e:
            logger.error(f"Failed to record consent audit: {e}")
            return False

    async def withdraw_consent(self, phone_hash: str) -> bool:
        """Handle DPDP Act consent revocation."""
        if not await self.ensure_connected() or self.collection is None:
            return False

        try:
            await self.collection.update_one(
                {"phone_hash": phone_hash},
                {
                    "$set": {
                        "consent_audit.consent_withdrawn": True,
                        "consent_audit.withdrawal_timestamp": datetime.now(
                            timezone.utc
                        ),
                        "dpiu_prefill_status": "CONSENT_WITHDRAWN_FROZEN",
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            logger.info(f"DPDP consent revoked for {phone_hash[:8]}...")
            return True
        except PyMongoError as e:
            logger.error(f"Failed to withdraw consent for {phone_hash[:8]}: {e}")
            return False

    async def process_enterprise_routing(
        self,
        phone_hash: str,
        enterprise: EnterpriseAspirations,
    ) -> dict[str, Any]:
        """
        Evaluate enterprise capital requirements and route to appropriate credit or subsidy scheme:
        1. Capital Subsidy (PM-AJAY GIA): Under 50k, eligible for grant up to 50k.
        2. Small Credit: 50k to 2 Lakh -> NSFDC Micro-Credit Desk.
        3. Medium Credit: 2 Lakh to 5 Lakh -> Mudra Kishore Portal.
        """
        await self.ensure_connected()

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
            "updated_at": datetime.now(timezone.utc),
        }

        if self._client.is_connected and self.collection is not None and phone_hash:
            try:
                await self.collection.update_one(
                    {"phone_hash": phone_hash},
                    {"$set": routing_record},
                    upsert=True,
                )
                logger.info(
                    f"Updated beneficiary {phone_hash[:8]} with GIA/credit routing: {credit_routing}"
                )
            except PyMongoError:
                logger.exception("Failed to update beneficiary enterprise routing")

        return routing_record
