"""
Repositories for MongoDB collections in PM-AJAY Voice Assistant.
"""

from .base_repository import BaseRepository
from .course_repo import CourseRepository
from .beneficiary_repo import BeneficiaryRepository
from .session_repo import SessionRepository
from .district_repo import DistrictRepository
from .dpiu_repo import DpiuRepository

__all__ = [
    "BaseRepository",
    "CourseRepository",
    "BeneficiaryRepository",
    "SessionRepository",
    "DistrictRepository",
    "DpiuRepository",
]
