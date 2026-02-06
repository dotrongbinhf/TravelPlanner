"""
Test endpoints for validating communication between Python and .NET.
These endpoints are for testing purposes during development.
"""

from fastapi import APIRouter, HTTPException
from src.models.schemas import TestRequest, TestResponse, DotNetRequest, DotNetResponse
from src.services.dotnet_client import dotnet_client
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/test", tags=["Testing"])


@router.post("/echo", response_model=TestResponse)
async def echo(request: TestRequest):
    """
    Echo endpoint - simply returns the received data.
    This allows .NET to test calling the Python API.
    
    Args:
        request: Test request with message and optional data
        
    Returns:
        TestResponse echoing back the received data
    """
    logger.info(f"Echo endpoint called with message: {request.message}")
    
    return TestResponse(
        success=True,
        message=f"Echo: {request.message}",
        data={
            "received": request.dict(),
            "echo": request.message
        },
        timestamp=datetime.now()
    )


@router.get("/call-dotnet", response_model=DotNetResponse)
async def call_dotnet_api():
    """
    Test endpoint that calls the .NET API.
    This allows testing Python -> .NET communication.
    
    Returns:
        Response from the .NET API
    """
    logger.info("Testing call to .NET API")
    
    try:
        # Try to call a health endpoint on the .NET API
        result = await dotnet_client.get("/health")
        
        return DotNetResponse(
            success=result.get("success", False),
            status_code=result.get("status_code", 500),
            data=result.get("data"),
            error=result.get("error")
        )
        
    except Exception as e:
        logger.error(f"Error calling .NET API: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to call .NET API: {str(e)}"
        )


@router.post("/call-dotnet-custom", response_model=DotNetResponse)
async def call_dotnet_custom(request: DotNetRequest):
    """
    Call a custom endpoint on the .NET API.
    Allows flexible testing of different .NET endpoints.
    
    Args:
        request: Specification of which .NET endpoint to call
        
    Returns:
        Response from the .NET API
    """
    logger.info(f"Calling .NET endpoint: {request.method} {request.endpoint}")
    
    try:
        method = request.method.upper()
        
        if method == "GET":
            result = await dotnet_client.get(request.endpoint)
        elif method == "POST":
            result = await dotnet_client.post(request.endpoint, request.data)
        elif method == "PUT":
            result = await dotnet_client.put(request.endpoint, request.data)
        elif method == "DELETE":
            result = await dotnet_client.delete(request.endpoint)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported HTTP method: {method}")
        
        return DotNetResponse(
            success=result.get("success", False),
            status_code=result.get("status_code", 500),
            data=result.get("data"),
            error=result.get("error")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calling .NET API: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to call .NET API: {str(e)}"
        )


@router.post("/process", response_model=TestResponse)
async def process_with_dotnet(request: TestRequest):
    """
    Process data and optionally communicate with .NET API.
    This simulates a workflow where Python receives data, processes it,
    and may interact with .NET API as part of the processing.
    
    Args:
        request: Test request with data to process
        
    Returns:
        Processed result
    """
    logger.info(f"Processing request: {request.message}")
    
    # Simulate some processing
    processed_data = {
        "original_message": request.message,
        "processed_at": datetime.now().isoformat(),
        "processing_result": "Data processed successfully"
    }
    
    # Optionally call .NET API (for demonstration)
    dotnet_result = None
    if request.data and request.data.get("call_dotnet"):
        try:
            dotnet_result = await dotnet_client.get("/health")
            processed_data["dotnet_called"] = True
            processed_data["dotnet_response"] = dotnet_result
        except Exception as e:
            logger.warning(f"Failed to call .NET API during processing: {e}")
            processed_data["dotnet_called"] = False
            processed_data["dotnet_error"] = str(e)
    
    return TestResponse(
        success=True,
        message="Data processed successfully",
        data=processed_data,
        timestamp=datetime.now()
    )
