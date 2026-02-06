"""
HTTP client for communicating with the .NET API.
Provides methods to make requests to the .NET backend.
"""

import httpx
from typing import Any, Optional
from src.config import settings
import logging

logger = logging.getLogger(__name__)


class DotNetClient:
    """Client for making HTTP requests to the .NET API."""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the .NET API client.
        
        Args:
            base_url: Base URL of the .NET API. Defaults to settings.DOTNET_API_URL
        """
        self.base_url = base_url or settings.DOTNET_API_URL
        self.timeout = 30.0
        
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Make an HTTP request to the .NET API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            
        Returns:
            Response data as dictionary
            
        Raises:
            httpx.HTTPError: If the request fails
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        logger.info(f"Making {method} request to {url}")
        
        async with httpx.AsyncClient(verify=False, timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params
                )
                response.raise_for_status()
                
                # Try to parse JSON response
                try:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "data": response.json()
                    }
                except Exception:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "data": {"text": response.text}
                    }
                    
            except httpx.HTTPError as e:
                logger.error(f"HTTP error occurred: {e}")
                return {
                    "success": False,
                    "status_code": getattr(e.response, 'status_code', 500) if hasattr(e, 'response') else 500,
                    "error": str(e)
                }
            except Exception as e:
                logger.error(f"Unexpected error occurred: {e}")
                return {
                    "success": False,
                    "status_code": 500,
                    "error": str(e)
                }
    
    async def health_check(self) -> bool:
        """
        Check if the .NET API is reachable.
        
        Returns:
            True if the API is reachable, False otherwise
        """
        try:
            result = await self._make_request("GET", "/health")
            return result.get("success", False)
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def get(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Make a GET request to the .NET API."""
        return await self._make_request("GET", endpoint, params=params)
    
    async def post(self, endpoint: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Make a POST request to the .NET API."""
        return await self._make_request("POST", endpoint, data=data)
    
    async def put(self, endpoint: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Make a PUT request to the .NET API."""
        return await self._make_request("PUT", endpoint, data=data)
    
    async def delete(self, endpoint: str) -> dict[str, Any]:
        """Make a DELETE request to the .NET API."""
        return await self._make_request("DELETE", endpoint)


# Global client instance
dotnet_client = DotNetClient()
