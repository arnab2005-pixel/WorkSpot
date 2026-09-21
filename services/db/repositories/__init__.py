"""
Repositories for MongoDB collections in PM-AJAY Voice Assistant.
"""

from .base_repository import BaseRepository
from .beneficiary_repo import BeneficiaryRepository
from .course_repo import CourseRepository
from .district_repo import DistrictRepository
from .dpiu_repo import DpiuRepository
from .session_repo import SessionRepository

__all__ = [
    "BaseRepository",
    "BeneficiaryRepository",
    "CourseRepository",
    "DistrictRepository",
    "DpiuRepository",
    "SessionRepository",
]
