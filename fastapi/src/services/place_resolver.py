"""
Shared Place Resolution Service.

Simple Text Search → DB lookup pipeline for resolving place names to Google Place data.
Used by Hotel Agent and Flight Agent for resolving their output places.

For LLM-verified resolution (attractions, transport hubs), use place_resolution_llm.py instead.
"""

import asyncio
import logging
from typing import Any, Optional

from src.tools.maps_tools import places_text_search_id_only
from src.tools.dotnet_tools import get_place_from_db

logger = logging.getLogger(__name__)


async def resolve_single_place(
    name: str,
    location_bias: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Resolve a single place name to full Google Place data.
    
    Pipeline: Text Search → top placeId → GET /api/place/{placeId} → full data.
    Returns dict with: placeId, title, address, location, openHours, etc.
    Returns None if resolution fails.
    """
    logger.info(f"[place_resolver] Resolving: '{name}'")

    # Step 1: Text Search → PlaceId
    try:
        search_results = await places_text_search_id_only.ainvoke({
            "query": name,
            "location_bias": location_bias or "",
        })
    except Exception as e:
        logger.error(f"[place_resolver] Text search failed for '{name}': {e}")
        return None

    if not search_results or not isinstance(search_results, list) or len(search_results) == 0:
        logger.warning(f"[place_resolver] No results for '{name}'")
        return None

    if isinstance(search_results[0], dict) and "error" in search_results[0]:
        logger.error(f"[place_resolver] Search error for '{name}': {search_results[0]['error']}")
        return None

    place_id = search_results[0].get("place_id", "")
    if not place_id:
        logger.warning(f"[place_resolver] No PlaceId for '{name}'")
        return None

    logger.info(f"[place_resolver] Found PlaceId: {place_id} for '{name}'")

    # Step 2: GET /api/place/{placeId} → .NET auto-ensures
    try:
        db_result = await get_place_from_db.ainvoke({"place_id": place_id})
    except Exception as e:
        logger.error(f"[place_resolver] DB lookup failed for '{name}' (placeId={place_id}): {e}")
        return None

    if isinstance(db_result, dict) and db_result.get("success"):
        place_data = db_result.get("data", {})
        place_data["_resolved_name"] = name
        logger.info(f"[place_resolver] Resolved: '{name}' → '{place_data.get('title', 'unknown')}' (placeId={place_id})")
        return place_data

    logger.warning(f"[place_resolver] Could not resolve '{name}' (placeId={place_id})")
    return None


async def resolve_places_batch(
    names: list[str],
    location_bias: Optional[str] = None,
    max_concurrent: int = 5,
) -> list[Optional[dict[str, Any]]]:
    """
    Resolve multiple place names concurrently.
    
    Returns list of resolved place data (same order as input).
    None entries indicate failed resolution.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _resolve_with_limit(name: str) -> Optional[dict]:
        async with semaphore:
            return await resolve_single_place(name, location_bias)

    results = await asyncio.gather(*[_resolve_with_limit(n) for n in names])
    return list(results)
