"""
.NET Backend API Tools.

Provides LangChain-compatible tools that call the .NET backend API
for hotel search, flight search, airport search, weather, place CRUD,
itinerary management, notes, expenses, and packing lists.
"""

import logging
from typing import Any, Optional
from langchain_core.tools import tool
from src.services.dotnet_client import dotnet_client

logger = logging.getLogger(__name__)


# ============================================================
# Hotel Tools
# ============================================================

@tool
async def search_hotels(
    query: str,
    check_in_date: str,
    check_out_date: str,
    adults: int = 2,
    children: int = 0,
    children_ages: Optional[str] = None,
    currency: str = "USD",
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    hotel_class: Optional[str] = None,
    sort_by: Optional[int] = None,
) -> dict[str, Any]:
    """Search for hotels using Google Hotels API via the .NET backend.
    
    Args:
        query: Search query (e.g. "Hotels in Da Nang", "Bali Resorts").
        check_in_date: Check-in date in YYYY-MM-DD format.
        check_out_date: Check-out date in YYYY-MM-DD format.
        adults: Number of adults (default 2).
        children: Number of children (default 0).
        children_ages: Ages of children, comma-separated (e.g. "5" or "5,8,10"). REQUIRED when children > 0. Count must match children parameter.
        currency: Currency code (default "USD").
        min_price: Minimum price filter.
        max_price: Maximum price filter.
        hotel_class: Star rating filter, comma-separated ("3,4,5").
        sort_by: Sort order (3=Lowest price, 8=Highest rating, 13=Most reviewed).

    Returns:
        Hotel search results from SerpApi.
    """
    params: dict[str, Any] = {
        "q": query,
        "checkInDate": check_in_date,
        "checkOutDate": check_out_date,
        "adults": adults,
        "children": children,
        "currency": currency,
    }
    if children_ages:
        params["childrenAges"] = children_ages
    if min_price is not None:
        params["minPrice"] = min_price
    if max_price is not None:
        params["maxPrice"] = max_price
    if hotel_class:
        params["hotelClass"] = hotel_class
    if sort_by is not None:
        params["sortBy"] = sort_by

    logger.info(f"[search_hotels] query={query}, dates={check_in_date}→{check_out_date}")
    result = await dotnet_client.get("/api/hotel/search", params=params)
    return result


# ============================================================
# Flight Tools
# ============================================================

@tool
async def search_airports(
    lat: float,
    lon: float,
    radius_km: int = 100,
    limit: int = 5,
) -> dict[str, Any]:
    """Search for airports near a geographic location.
    
    Args:
        lat: Latitude of the location.
        lon: Longitude of the location.
        radius_km: Search radius in kilometers (default 100).
        limit: Maximum number of results (default 5).

    Returns:
        List of nearby airports with IATA codes.
    """
    params = {
        "lat": lat,
        "lon": lon,
        "radiusKm": radius_km,
        "limit": limit,
        "withFlightInfoOnly": True,
    }
    logger.info(f"[search_airports] lat={lat}, lon={lon}, radius={radius_km}km")
    result = await dotnet_client.get("/api/flight/airports", params=params)
    return result


@tool
async def search_flights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: Optional[str] = None,
    flight_type: int = 2,
    adults: int = 1,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
    travel_class: int = 1,
    currency: str = "USD",
    stops: Optional[int] = None,
    max_price: Optional[int] = None,
    outbound_times: Optional[str] = None,
    return_times: Optional[str] = None,
    departure_token: Optional[str] = None,
) -> dict[str, Any]:
    """Search for flights between airports.
    
    Args:
        departure_id: Departure airport IATA code (e.g. "SGN", "HAN").
        arrival_id: Arrival airport IATA code (e.g. "DAD", "HND").
        outbound_date: Departure date in YYYY-MM-DD format.
        return_date: Return date in YYYY-MM-DD format. ONLY for round trips (flight_type=1). Do NOT provide this for one-way flights (flight_type=2).
        flight_type: 1=Round trip, 2=One way, 3=Multi-city.
        adults: Number of adult passengers.
        children: Number of child passengers.
        infants_in_seat: Number of infants in seat.
        infants_on_lap: Number of infants on lap.
        travel_class: 1=Economy, 2=Premium economy, 3=Business, 4=First.
        currency: Currency code.
        stops: 0=Any, 1=Nonstop, 2=1 stop or fewer, 3=2 stops or fewer.
        max_price: Maximum ticket price.
        outbound_times: Outbound times range. Two or four comma-separated numbers representing hours 0-23
        return_times: Return times range. Same format as outbound_times.
        departure_token: Token from outbound flight to search for return flights (round trip only).

    Returns:
        Flight search results from SerpApi.
    """
    params: dict[str, Any] = {
        "departureId": departure_id,
        "arrivalId": arrival_id,
        "outboundDate": outbound_date,
        "type": flight_type,
        "adults": adults,
        "children": children,
        "infantsInSeat": infants_in_seat,
        "infantsOnLap": infants_on_lap,
        "travelClass": travel_class,
        "currency": currency,
    }
    if return_date:
        params["returnDate"] = return_date
    if stops is not None:
        params["stops"] = stops
    if max_price is not None:
        params["maxPrice"] = max_price
    if outbound_times:
        params["outboundTimes"] = outbound_times
    if return_times:
        params["returnTimes"] = return_times
    if departure_token:
        params["departureToken"] = departure_token

    logger.info(f"[search_flights] {departure_id}→{arrival_id} on {outbound_date}")
    result = await dotnet_client.get("/api/flight/search", params=params)
    return result


# ============================================================
# Weather Tools
# ============================================================

@tool
async def get_weather_forecast(
    city: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    days: int = 7,
    units: str = "metric",
) -> dict[str, Any]:
    """Get daily weather forecast (up to 16 days) for a location.
    
    Args:
        city: City name (e.g. "Da Nang", "Hanoi,VN"). Either city or lat+lon required.
        lat: Latitude. Required if city is not provided.
        lon: Longitude. Required if city is not provided.
        days: Number of forecast days (1-16, default 7).
        units: "metric" (Celsius) or "imperial" (Fahrenheit).

    Returns:
        Daily weather forecast data.
    """
    params: dict[str, Any] = {"units": units, "cnt": days}
    if city:
        params["q"] = city
    elif lat is not None and lon is not None:
        params["lat"] = lat
        params["lon"] = lon
    else:
        return {"error": "Either city name or lat+lon must be provided"}

    logger.info(f"[get_weather_forecast] location={city or f'{lat},{lon}'}, days={days}")
    result = await dotnet_client.get("/api/weather/daily", params=params)
    return result


# ============================================================
# Place Tools
# ============================================================

@tool
async def get_place_from_db(place_id: str) -> dict[str, Any]:
    """Get a place from the database by its Google Place ID.
    
    Args:
        place_id: Google Place ID string.

    Returns:
        Place data if found, or error with status 404 if not found.
    """
    logger.info(f"[get_place_from_db] Fetching placeId={place_id} from DB")
    result = await dotnet_client.get(f"/api/place/{place_id}")
        
    return result


@tool
async def create_place_in_db(place_data: dict[str, Any]) -> dict[str, Any]:
    """Create a new place in the database.
    
    Args:
        place_data: Place data dict matching the Place schema:
            - placeId: Google Place ID
            - title: Display name
            - category: Place type/category
            - location: GeoJSON {type: "Point", coordinates: [lng, lat]}
            - address: Formatted address
            - openHours: Opening hours per day
            - website: Website URL
            - reviewCount: Number of reviews
            - reviewRating: Average rating
            - link: Google Maps link

    Returns:
        Created place data.
    """
    logger.info(f"[create_place_in_db] placeId={place_data.get('placeId', 'unknown')}")
    result = await dotnet_client.post("/api/place", data=place_data)
    return result

