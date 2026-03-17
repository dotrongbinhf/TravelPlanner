"""
Google Maps Platform Tools.

Provides tools for:
- Places Text Search (ID-only mode for place resolution)
- Place Details (for ensure-place fallback)
- Nearby Search (restaurants, attractions near a location)
- Distance Matrix (travel times between locations for VRP)
"""

import logging
from typing import Any, Optional
from langchain_core.tools import tool
import googlemaps
from src.config import settings

logger = logging.getLogger(__name__)

_gmaps_client: Optional[googlemaps.Client] = None


def _get_gmaps_client() -> googlemaps.Client:
    global _gmaps_client
    if _gmaps_client is None:
        _gmaps_client = googlemaps.Client(key=settings.GOOGLE_MAPS_API_KEY)
    return _gmaps_client


@tool
async def places_text_search_id_only(
    query: str,
    location_bias: Optional[str] = None,
) -> list[dict[str, str]]:
    """Search for places by text query and return only Place IDs.
    
    This is the first step in the Place Resolution Pipeline:
    1. Search by name → get PlaceId
    2. Use PlaceId[0] (highest relevance) for DB lookup
    
    Args:
        query: Place name or search text (e.g. "Ba Na Hills Da Nang", "Pho 2000 Ho Chi Minh").
        location_bias: Optional location bias as "lat,lng" to prefer results near this location.

    Returns:
        List of places with placeId and name, ordered by relevance.
    """
    logger.info(f"[places_text_search_id_only] query='{query}'")
    try:
        client = _get_gmaps_client()
        kwargs: dict[str, Any] = {"query": query}
        if location_bias:
            parts = location_bias.split(",")
            if len(parts) == 2:
                kwargs["location"] = (float(parts[0]), float(parts[1]))
                kwargs["radius"] = 50000  # 50km bias radius

        results = client.places(
            **kwargs,
        )

        places = []
        for place in results.get("results", [])[:5]:
            places.append({
                "place_id": place.get("place_id", ""),
                "name": place.get("name", ""),
                "address": place.get("formatted_address", ""),
                "types": ",".join(place.get("types", [])),
            })

        logger.info(f"[places_text_search_id_only] found {len(places)} results")
        return places
    except Exception as e:
        logger.error(f"[places_text_search_id_only] error: {e}")
        return [{"error": str(e)}]


@tool
async def get_google_place_details(place_id: str) -> dict[str, Any]:
    """Get detailed information about a place from Google Places API.
    
    This is used in the ensure-place fallback: when a place is NOT found
    in the database, we fetch its details from Google and save it.
    
    Args:
        place_id: Google Place ID.

    Returns:
        Place details including name, address, location, opening hours, rating, etc.
    """
    logger.info(f"[get_google_place_details] placeId={place_id}")
    try:
        client = _get_gmaps_client()
        result = client.place(
            place_id=place_id,
            fields=[
                "place_id", "name", "formatted_address", "geometry",
                "type", "rating", "user_ratings_total", "opening_hours",
                "website", "url",
            ],
        )

        place = result.get("result", {})
        geometry = place.get("geometry", {}).get("location", {})
        
        # Parse opening hours into our format
        open_hours = {
            "monday": [], "tuesday": [], "wednesday": [],
            "thursday": [], "friday": [], "saturday": [], "sunday": [],
        }
        day_keys = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        
        opening_hours = place.get("opening_hours", {})
        for period in opening_hours.get("periods", []):
            open_info = period.get("open", {})
            close_info = period.get("close", {})
            if open_info and close_info:
                day_idx = open_info.get("day", 0)
                if 0 <= day_idx < 7:
                    day_key = day_keys[day_idx]
                    open_time = open_info.get("time", "0000")
                    close_time = close_info.get("time", "2359")
                    open_hours[day_key].append(f"{open_time[:2]}:{open_time[2:]}-{close_time[:2]}:{close_time[2:]}")

        place_data = {
            "placeId": place.get("place_id", place_id),
            "link": place.get("url", f"https://www.google.com/maps/place/?q=place_id:{place_id}"),
            "title": place.get("name", ""),
            "category": place.get("types", ["point_of_interest"])[0] if place.get("types") else "point_of_interest",
            "location": {
                "type": "Point",
                "coordinates": [geometry.get("lng", 0), geometry.get("lat", 0)],
            },
            "address": place.get("formatted_address", ""),
            "openHours": open_hours,
            "website": place.get("website", ""),
            "reviewCount": place.get("user_ratings_total", 0),
            "reviewRating": place.get("rating", 0),
            "reviewsPerRating": {},
            "cid": "",
            "description": "",
            "thumbnail": "https://placehold.co/600x400?text=No+Image",
            "images": [],
            "userReviews": [],
        }

        logger.info(f"[get_google_place_details] resolved: {place_data['title']}")
        return place_data
    except Exception as e:
        logger.error(f"[get_google_place_details] error: {e}")
        return {"error": str(e)}


@tool
async def places_nearby_search(
    lat: float,
    lng: float,
    radius: int = 2000,
    place_type: str = "restaurant",
    keyword: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Search for places near a specific location.
    
    Args:
        lat: Latitude of the center point.
        lng: Longitude of the center point.
        radius: Search radius in meters (default 2000m = 2km).
        place_type: Google Place type (e.g. "restaurant", "tourist_attraction", "cafe").
        keyword: Optional keyword to filter results (e.g. "seafood", "Vietnamese").

    Returns:
        List of nearby places with basic info.
    """
    logger.info(f"[places_nearby_search] ({lat},{lng}), type={place_type}, keyword={keyword}")
    try:
        client = _get_gmaps_client()
        kwargs: dict[str, Any] = {
            "location": (lat, lng),
            "radius": radius,
            "type": place_type,
        }
        if keyword:
            kwargs["keyword"] = keyword

        results = client.places_nearby(**kwargs)

        places = []
        for p in results.get("results", [])[:10]:
            geo = p.get("geometry", {}).get("location", {})
            places.append({
                "place_id": p.get("place_id", ""),
                "name": p.get("name", ""),
                "address": p.get("vicinity", ""),
                "rating": p.get("rating", 0),
                "user_ratings_total": p.get("user_ratings_total", 0),
                "types": p.get("types", []),
                "lat": geo.get("lat", 0),
                "lng": geo.get("lng", 0),
            })

        logger.info(f"[places_nearby_search] found {len(places)} nearby places")
        return places
    except Exception as e:
        logger.error(f"[places_nearby_search] error: {e}")
        return [{"error": str(e)}]


@tool
async def get_distance_matrix(
    origins: list[str],
    destinations: list[str],
    mode: str = "driving",
) -> dict[str, Any]:
    """Get travel times and distances between multiple locations.
    
    This is used to build the travel time matrix for VRP optimization.
    
    Args:
        origins: List of origin locations as "lat,lng" strings.
        destinations: List of destination locations as "lat,lng" strings.
        mode: Travel mode ("driving", "walking", "transit", "bicycling").

    Returns:
        Matrix of travel durations (in minutes) and distances.
    """
    logger.info(f"[get_distance_matrix] {len(origins)} origins × {len(destinations)} destinations")
    try:
        client = _get_gmaps_client()
        result = client.distance_matrix(
            origins=origins,
            destinations=destinations,
            mode=mode,
            language="en",
        )

        # Parse into a simplified matrix
        duration_matrix: list[list[int]] = []
        for row in result.get("rows", []):
            durations = []
            for element in row.get("elements", []):
                if element.get("status") == "OK":
                    # Convert seconds to minutes
                    durations.append(element["duration"]["value"] // 60)
                else:
                    durations.append(9999)  # Unreachable
            duration_matrix.append(durations)

        return {
            "duration_matrix_minutes": duration_matrix,
            "origin_addresses": result.get("origin_addresses", []),
            "destination_addresses": result.get("destination_addresses", []),
        }
    except Exception as e:
        logger.error(f"[get_distance_matrix] error: {e}")
        return {"error": str(e)}
