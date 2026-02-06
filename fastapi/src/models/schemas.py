"""
Models and schemas for API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


# Health check models
class HealthResponse(BaseModel):
    """Response model for health check endpoints."""
    status: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    details: Optional[dict[str, Any]] = None


# Test endpoint models
class TestRequest(BaseModel):
    """Generic test request model."""
    message: str
    data: Optional[dict[str, Any]] = None


class TestResponse(BaseModel):
    """Generic test response model."""
    success: bool
    message: str
    data: Optional[dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)


# .NET API models
class DotNetRequest(BaseModel):
    """Model for requests to .NET API."""
    endpoint: str
    method: str = "GET"
    data: Optional[dict[str, Any]] = None


class DotNetResponse(BaseModel):
    """Model for responses from .NET API."""
    success: bool
    status_code: int
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
