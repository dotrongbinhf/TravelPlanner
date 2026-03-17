"""
Place Resolution Pipeline.

Mirrors the frontend use-ensure-place.ts pattern:
1. Place name → Google Places Text Search → PlaceId[0]
2. PlaceId → DB lookup via .NET
3. If 404 → Google Place Details → Create in DB

This ensures every place referenced by agents exists in the database
with full data before being used in itineraries.
"""

import logging
from typing import Any, Optional
from src.tools.maps_tools import places_text_search_id_only, get_google_place_details
from src.tools.dotnet_tools import get_place_from_db, create_place_in_db

logger = logging.getLogger(__name__)


async def resolve_place(
    place_name: str,
    location_bias: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve a place name to a fully-populated Place record in the database.
    
    Pipeline:
    1. Text Search (ID-only) → get Google PlaceId for the place name
    2. Look up PlaceId in DB via .NET GET /api/place/{placeId}
    3. If not found (404): fetch details from Google Places API, create in DB
    
    Args:
        place_name: Human-readable name of the place (e.g. "Ba Na Hills").
        location_bias: Optional "lat,lng" string to bias search toward a location.
        
    Returns:
        Place data dict from the database, or error dict if resolution failed.
    """
    logger.info(f"[resolve_place] Resolving: '{place_name}'")
    
    # Step 1: Text Search → PlaceId
    search_results = await places_text_search_id_only.ainvoke({
        "query": place_name,
        "location_bias": location_bias or "",
    })
    
    if not search_results or (isinstance(search_results, list) and len(search_results) == 0):
        logger.warning(f"[resolve_place] No results for '{place_name}'")
        return {"error": f"Could not find place: {place_name}", "resolved": False}
    
    if isinstance(search_results[0], dict) and "error" in search_results[0]:
        return {"error": search_results[0]["error"], "resolved": False}
    
    # Use first result (highest relevance)
    place_id = search_results[0].get("place_id", "")
    place_search_name = search_results[0].get("name", place_name)
    
    if not place_id:
        return {"error": f"No PlaceId found for '{place_name}'", "resolved": False}
    
    logger.info(f"[resolve_place] Found PlaceId: {place_id} ({place_search_name})")
    
    # Step 2: DB lookup
    db_result = await get_place_from_db.ainvoke({"place_id": place_id})
    
    if isinstance(db_result, dict) and db_result.get("success") and db_result.get("status_code") == 200:
        logger.info(f"[resolve_place] Found in DB: {place_search_name}")
        place_data = db_result.get("data", {})
        place_data["resolved"] = True
        place_data["source"] = "database"
        return place_data
    
    # Step 3: Not in DB → fetch from Google and create
    logger.info(f"[resolve_place] Not in DB, fetching from Google Places API...")
    
    google_details = await get_google_place_details.ainvoke({"place_id": place_id})
    
    if isinstance(google_details, dict) and "error" in google_details:
        return {"error": google_details["error"], "resolved": False}
    
    # Create in DB
    create_result = await create_place_in_db.ainvoke({"place_data": google_details})
    
    if isinstance(create_result, dict) and create_result.get("success"):
        logger.info(f"[resolve_place] Created in DB: {place_search_name}")
        created_data = create_result.get("data", google_details)
        created_data["resolved"] = True
        created_data["source"] = "google_places_api"
        return created_data
    
    # If create fails (maybe already exists due to race condition), try fetching again
    logger.warning(f"[resolve_place] Create failed, retrying DB fetch...")
    retry_result = await get_place_from_db.ainvoke({"place_id": place_id})
    if isinstance(retry_result, dict) and retry_result.get("success"):
        place_data = retry_result.get("data", {})
        place_data["resolved"] = True
        place_data["source"] = "database_retry"
        return place_data
    
    # Last resort: return Google data without DB persistence
    google_details["resolved"] = True
    google_details["source"] = "google_places_api_no_db"
    return google_details


async def resolve_places(
    place_names: list[str],
    location_bias: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Resolve multiple place names to database records.
    
    Args:
        place_names: List of place names to resolve.
        location_bias: Optional "lat,lng" to bias searches.
        
    Returns:
        List of resolved place data dicts.
    """
    results = []
    for name in place_names:
        result = await resolve_place(name, location_bias)
        results.append(result)
    return results
