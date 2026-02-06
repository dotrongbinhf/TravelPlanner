"""
Health check endpoints.
Provides status information about the API and its dependencies.
"""

from fastapi import APIRouter, HTTPException
from src.models.schemas import HealthResponse
from src.services.dotnet_client import dotnet_client
from datetime import datetime

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns:
        HealthResponse with status information
    """
    return HealthResponse(
        status="healthy",
        message="FastAPI service is running",
        timestamp=datetime.now(),
        details={
            "service": "fastapi-multi-agent",
            "version": "1.0.0"
        }
    )

@router.get("/circle", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns:
        HealthResponse with status information
    """

    response = await dotnet_client.health_check()

    if(response):
        return HealthResponse(
            status="healthy",
            message="dotnet is healthy",
            timestamp=datetime.now(),
            details={
                "service": "fastapi-multi-agent",
                "version": "1.0.0"
            }
        )
    else:
        return HealthResponse(
            status="unhealthy",
            message="dotnet is unhealthy",
            timestamp=datetime.now(),
            details={
                "service": "fastapi-multi-agent",
                "version": "1.0.0"
            }
        )


@router.get("/dotnet", response_model=HealthResponse)
async def dotnet_health_check():
    """
    Check connectivity to the .NET API.
    
    Returns:
        HealthResponse with .NET API status
        
    Raises:
        HTTPException: If .NET API is unreachable
    """
    is_healthy = await dotnet_client.health_check()
    
    if is_healthy:
        return HealthResponse(
            status="healthy",
            message=".NET API is reachable",
            timestamp=datetime.now(),
            details={
                "dotnet_api_url": dotnet_client.base_url
            }
        )
    else:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "message": ".NET API is not reachable",
                "dotnet_api_url": dotnet_client.base_url
            }
        )
