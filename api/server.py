"""
Main FastAPI application server for PM-AJAY Voice Assistant.

Wires:
- Frontend mock endpoints (/api/v1/mock/...)
- Telephony WebSocket gateway (/ws/media/{session_id})
- Static audio assets (/static/...)
- Health check endpoints
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.config import get_settings
import logging
from api.routes_mock import router as mock_router
from api.routes_telephony_ws import router as ws_router
from api.routes_client import router as client_router, fsm

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and graceful shutdown."""
    # Ensure static directories exist
    static_dir = Path(__file__).parent.parent / "static" / "audio"
    static_dir.mkdir(parents=True, exist_ok=True)

    # Connect MongoDB service
    try:
        await fsm.mongo_service.connect()
        logger.info(f"Connected to MongoDB: {fsm.mongo_service._connected}")
    except Exception as exc:  # noqa: BLE001 - MongoDB connection is optional
        logger.warning("MongoDB connection notice: %s", exc)

    # Connect Redis session cache
    try:
        await fsm.session_cache.connect()
        logger.info(f"Connected to Redis: {fsm.session_cache._connected}")
    except Exception as exc:  # noqa: BLE001 - Redis connection is optional
        logger.warning("Redis connection notice: %s", exc)

    yield

    # Graceful teardown
    if fsm.mongo_service:
        await fsm.mongo_service.close()
    if fsm.session_cache:
        await fsm.session_cache.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="PM-AJAY Multilingual Voice Virtual Livelihood Assistant Core Backend",
    lifespan=lifespan,
)

# CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static audio files
static_path = Path(__file__).parent.parent / "static"
static_path.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Register routers
app.include_router(client_router, prefix="/api/v1")
app.include_router(client_router, prefix="", tags=["client-alias"])
app.include_router(mock_router)
app.include_router(ws_router)

@app.get("/health")
async def health_check():
    """Healthcheck endpoint reporting database and assistant status."""
    mongo_connected = bool(fsm.mongo_service and fsm.mongo_service._connected)
    redis_connected = bool(fsm.session_cache and fsm.session_cache._connected)
    return {
        "status": "healthy" if (mongo_connected and redis_connected) else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "database": {
            "mongodb": "connected" if mongo_connected else "in_memory_or_offline_fallback",
            "redis": "connected" if redis_connected else "in_memory_fallback",
        },
    }


@app.get("/api/info")
async def api_info():
    """API info endpoint."""
    return {
        "message": "PM-AJAY Voice Virtual Livelihood Assistant Core API",
        "docs_url": "/docs",
        "mock_start_url": "/api/v1/mock/session/start",
        "telephony_ws_url": "/ws/media/{session_id}",
    }


# Mount frontend build SPA if available (evaluated after all API endpoints)
web_dist_path = Path(__file__).parent.parent / "apps" / "web" / "dist"
if web_dist_path.exists():
    app.mount("/", StaticFiles(directory=str(web_dist_path), html=True), name="frontend")
else:
    @app.get("/")
    async def root():
        """Root info endpoint when frontend is not built."""
        return {
            "message": "PM-AJAY Voice Virtual Livelihood Assistant Core API",
            "docs_url": "/docs",
            "mock_start_url": "/api/v1/mock/session/start",
            "telephony_ws_url": "/ws/media/{session_id}",
        }


if __name__ == "__main__":
    import uvicorn
    listen_port = int(os.environ.get("PORT", settings.port))
    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=listen_port,
        reload=settings.debug,
    )
