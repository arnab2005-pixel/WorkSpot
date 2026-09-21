"""
Database subsystem for PM-AJAY Voice Assistant.

Provides async MongoDB connectivity, Atlas Vector Search, indexing,
and repository pattern data access layer.
"""

from .indexes import ensure_indexes
from .mongo_client import MongoDBClient, get_mongo_client

__all__ = ["MongoDBClient", "ensure_indexes", "get_mongo_client"]
