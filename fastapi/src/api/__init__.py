"""API routes package initialization."""

from fastapi import APIRouter
from .routes import health, test

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(health.router)
api_router.include_router(test.router)

__all__ = ["api_router"]
