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
from api.routes_mock import router as mock_router
from api.routes_telephony_ws import router as ws_router
from api.routes_client import router as client_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and graceful shutdown."""
    # Ensure static directories exist
    static_dir = Path(__file__).parent.parent / "static" / "audio"
    static_dir.mkdir(parents=True, exist_ok=True)
    yield


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
app.include_router(client_router)
app.include_router(client_router, prefix="", tags=["client-alias"])
app.include_router(mock_router)
app.include_router(ws_router)


@app.get("/health")
async def health_check():
    """Healthcheck endpoint for Docker container orchestration."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/")
async def root():
    """Root info endpoint."""
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
