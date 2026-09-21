"""
Database subsystem for PM-AJAY Voice Assistant.

Provides async MongoDB connectivity, Atlas Vector Search, indexing,
and repository pattern data access layer.
"""

from .mongo_client import get_mongo_client, MongoDBClient
from .indexes import ensure_indexes

__all__ = ["get_mongo_client", "MongoDBClient", "ensure_indexes"]
