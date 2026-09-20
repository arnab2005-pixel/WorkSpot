"""
Recommendation module for PM-AJAY Voice Assistant.
"""

from .embedder import CourseEmbedder
from .mongo_service import MongoService

__all__ = ["CourseEmbedder", "MongoService"]
