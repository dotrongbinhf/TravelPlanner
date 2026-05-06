"""API routes package initialization."""

from fastapi import APIRouter
from .routes import health, test, agent_stream

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router)
api_router.include_router(test.router)
api_router.include_router(agent_stream.router)

__all__ = ["api_router"]
