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
    logger.info(f"[get_place_from_db] placeId={place_id}")
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


# ============================================================
# Itinerary CRUD Tools
# ============================================================

@tool
async def create_itinerary_item(
    itinerary_day_id: str,
    place_id: str,
    start_time: Optional[str] = None,
    duration: Optional[str] = None,
) -> dict[str, Any]:
    """Add a place to a specific itinerary day.
    
    Args:
        itinerary_day_id: ID of the itinerary day.
        place_id: MongoDB Object ID of the place (NOT Google Place ID).
        start_time: Start time in HH:mm format (optional).
        duration: Duration in HH:mm format (optional).

    Returns:
        Created itinerary item.
    """
    data: dict[str, Any] = {"placeId": place_id}
    if start_time:
        data["startTime"] = start_time
    if duration:
        # Convert HH:mm to TimeSpan format HH:mm:ss
        data["duration"] = f"{duration}:00" if len(duration) == 5 else duration

    logger.info(f"[create_itinerary_item] dayId={itinerary_day_id}, placeId={place_id}")
    result = await dotnet_client.post(
        f"/api/itineraryItem?itineraryDayId={itinerary_day_id}",
        data=data,
    )
    return result


@tool
async def update_itinerary_item(
    item_id: str,
    itinerary_day_id: Optional[str] = None,
    start_time: Optional[str] = None,
    duration: Optional[str] = None,
) -> dict[str, Any]:
    """Update an existing itinerary item (move to different day, change time/duration).
    
    Args:
        item_id: ID of the itinerary item to update.
        itinerary_day_id: New day ID (to move item to a different day).
        start_time: New start time in HH:mm format.
        duration: New duration in HH:mm format.

    Returns:
        Updated itinerary item.
    """
    data: dict[str, Any] = {}
    if itinerary_day_id:
        data["itineraryDayId"] = itinerary_day_id
    if start_time:
        data["startTime"] = start_time
    if duration:
        data["duration"] = f"{duration}:00" if len(duration) == 5 else duration

    logger.info(f"[update_itinerary_item] itemId={item_id}")
    result = await dotnet_client.patch(f"/api/itineraryItem/{item_id}", data=data)
    return result


@tool
async def delete_itinerary_item(item_id: str) -> dict[str, Any]:
    """Remove an itinerary item.
    
    Args:
        item_id: ID of the itinerary item to delete.

    Returns:
        Deletion confirmation.
    """
    logger.info(f"[delete_itinerary_item] itemId={item_id}")
    result = await dotnet_client.delete(f"/api/itineraryItem/{item_id}")
    return result


# ============================================================
# Note Tools
# ============================================================

@tool
async def create_note(
    plan_id: str,
    title: str,
    content: str,
) -> dict[str, Any]:
    """Create a travel note for a plan.
    
    Args:
        plan_id: ID of the plan.
        title: Note title.
        content: Note content text.

    Returns:
        Created note.
    """
    logger.info(f"[create_note] planId={plan_id}, title={title}")
    result = await dotnet_client.post(
        f"/api/note?planId={plan_id}",
        data={"title": title, "content": content},
    )
    return result


# ============================================================
# Expense Tools
# ============================================================

@tool
async def create_expense_item(
    plan_id: str,
    name: str,
    amount: float,
    category: int = 5,
) -> dict[str, Any]:
    """Add a budget expense item to a plan.
    
    Args:
        plan_id: ID of the plan.
        name: Expense description.
        amount: Expense amount in the plan's currency.
        category: Expense category (0=Food, 1=Transport, 2=Accommodation, 3=Activities, 4=Shopping, 5=Other).

    Returns:
        Created expense item.
    """
    logger.info(f"[create_expense_item] planId={plan_id}, name={name}, amount={amount}")
    result = await dotnet_client.post(
        f"/api/expenseItem?planId={plan_id}",
        data={"name": name, "amount": amount, "category": category},
    )
    return result


# ============================================================
# Packing List Tools
# ============================================================

@tool
async def create_packing_list(
    plan_id: str,
    name: str,
    items: list[str],
) -> dict[str, Any]:
    """Create a packing list with items for a plan.
    
    Args:
        plan_id: ID of the plan.
        name: Packing list name (e.g. "Essentials", "Clothing").
        items: List of item names to pack.

    Returns:
        Created packing list with items.
    """
    packing_items = [{"name": item, "isPacked": False} for item in items]
    logger.info(f"[create_packing_list] planId={plan_id}, name={name}, items={len(items)}")
    result = await dotnet_client.post(
        f"/api/packingList?planId={plan_id}",
        data={"name": name, "packingItems": packing_items},
    )
    return result


# ============================================================
# Plan Update Tools
# ============================================================

@tool
async def update_plan_info(
    plan_id: str,
    name: Optional[str] = None,
    budget: Optional[float] = None,
    currency_code: Optional[str] = None,
) -> dict[str, Any]:
    """Update basic plan information.
    
    Args:
        plan_id: ID of the plan.
        name: New plan name.
        budget: New total budget.
        currency_code: New currency code (e.g. "VND", "USD").

    Returns:
        Updated plan data.
    """
    data: dict[str, Any] = {}
    if name:
        data["name"] = name
    if budget is not None:
        data["budget"] = budget
    if currency_code:
        data["currencyCode"] = currency_code

    logger.info(f"[update_plan_info] planId={plan_id}, updates={list(data.keys())}")
    result = await dotnet_client.patch(f"/api/plan/{plan_id}", data=data)
    return result
