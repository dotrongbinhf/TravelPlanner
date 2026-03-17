"""
Tavily Web Search Tool.

Provides web search capability for travel research, cultural information,
attraction details, and travel tips.
"""

import logging
from typing import Optional
from langchain_core.tools import tool
from tavily import AsyncTavilyClient
from src.config import settings

logger = logging.getLogger(__name__)

_tavily_client: Optional[AsyncTavilyClient] = None


def _get_tavily_client() -> AsyncTavilyClient:
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
    return _tavily_client


@tool
async def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
) -> list[dict]:
    """Search the web for travel-related information using Tavily.
    
    Use this to research attractions, cultural information, travel tips,
    opening hours, seasonal events, local customs, or any specific details
    that the LLM doesn't have enough knowledge about.
    
    Args:
        query: Search query (e.g. "best beaches in Da Nang", "Da Nang weather in April").
        max_results: Maximum number of results (default 5).
        search_depth: "basic" for quick search, "advanced" for deeper research.

    Returns:
        List of search results with title, url, and content.
    """
    logger.info(f"[tavily_search] query='{query}', max_results={max_results}")
    try:
        client = _get_tavily_client()
        response = await client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
        )
        results = response.get("results", [])
        # Simplify results to reduce token usage
        simplified = []
        for r in results:
            simplified.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:500],  # Truncate long content
            })
        logger.info(f"[tavily_search] found {len(simplified)} results")
        return simplified
    except Exception as e:
        logger.error(f"[tavily_search] error: {e}")
        return [{"error": str(e)}]
