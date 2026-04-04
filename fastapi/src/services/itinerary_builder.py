"""
Itinerary Builder Service.

Pure-function pipeline that transforms agent outputs into VRP solver input:
1. Extract place names from flight/hotel/attraction agent outputs
2. Resolve each name to a Google Place ID via Text Search
3. Ensure each place exists in DB via .NET GET /api/place/{placeId} (auto-fetches from Google if missing)
4. Compute VRP time windows from opening hours + trip dates
5. Build VRP locations list and call solve_vrp()
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from src.tools.maps_tools import places_text_search_id_only
from src.tools.dotnet_tools import get_place_from_db
from src.tools.itinerary_tools import solve_vrp
from src.tools.maps_tools import LOCAL_TRANSPORT_MAP

logger = logging.getLogger(__name__)

# Day-of-week mapping: Python weekday() → OpenHours key
WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


# ============================================================================
# STEP 1: Extract place names from agent outputs
# ============================================================================

def extract_place_names(
    agent_outputs: dict[str, Any],
    plan_context: dict[str, Any] | None = None,
) -> dict[str, list[dict]]:
    """
    Extract place names from flight/hotel/attraction agent outputs.
    For non-flight trips, reads transport_hubs from plan_context.
    
    Returns:
        {
            "airports": [
                {"name": "...", "role": "outbound_departure", "time": "06:50"},
                {"name": "...", "role": "outbound_arrival", "time": "09:00"},
                {"name": "...", "role": "return_departure", "time": "16:50"},
                {"name": "...", "role": "return_arrival", "time": "19:00"},
            ],
            "hotels": [
                {"name": "...", "check_in": "2026-03-27", "check_out": "2026-03-30", "segment_name": "..."},
            ],
            "attractions": [
                {"name": "...", "suggested_duration_minutes": 60},
            ],
        }
    """
    result = {"airports": [], "hotels": [], "attractions": []}
    plan_context = plan_context or {}

    # --- Flight ---
    flight = agent_outputs.get("flight_agent", {})
    if flight and not flight.get("skipped"):
        # Outbound flight
        outbound = flight.get("recommend_outbound_flight", {})
        if outbound:
            result["airports"].append({
                "name": outbound.get("departure_airport_name", ""),
                "role": "outbound_departure",
                "time": outbound.get("departure_time", ""),
            })
            result["airports"].append({
                "name": outbound.get("arrival_airport_name", ""),
                "role": "outbound_arrival",
                "time": outbound.get("arrival_time", ""),
            })

        # Return flight
        return_flight = flight.get("recommend_return_flight", {})
        if return_flight:
            result["airports"].append({
                "name": return_flight.get("departure_airport_name", ""),
                "role": "return_departure",
                "time": return_flight.get("departure_time", ""),
            })
            result["airports"].append({
                "name": return_flight.get("arrival_airport_name", ""),
                "role": "return_arrival",
                "time": return_flight.get("arrival_time", ""),
            })

    # --- Non-flight: extract transport_hubs from mobility_plan ---
    if not result["airports"]:
        mobility_plan = plan_context.get("mobility_plan") or {}
        transport_hubs = mobility_plan.get("transport_hubs") or {}
        if transport_hubs:
            outbound_dep = transport_hubs.get("outbound_departure", "")
            outbound_arr = transport_hubs.get("outbound_arrival", "")
            return_dep = transport_hubs.get("return_departure", "")
            return_arr = transport_hubs.get("return_arrival", "")
            # Use ready_time for outbound (when traveler can start exploring)
            outbound_ready = transport_hubs.get("outbound_ready_time", "07:00")
            return_dep_time = transport_hubs.get("return_departure_time", "15:00")

            if outbound_dep:
                result["airports"].append({
                    "name": outbound_dep,
                    "role": "outbound_departure",
                    "time": outbound_ready,
                })
            if outbound_arr:
                result["airports"].append({
                    "name": outbound_arr,
                    "role": "outbound_arrival",
                    "time": outbound_ready,
                })
            if return_dep:
                result["airports"].append({
                    "name": return_dep,
                    "role": "return_departure",
                    "time": return_dep_time,
                })
            if return_arr:
                result["airports"].append({
                    "name": return_arr,
                    "role": "return_arrival",
                    "time": return_dep_time,
                })

    # --- Hotel ---
    hotel = agent_outputs.get("hotel_agent", {})
    if hotel and not hotel.get("skipped"):
        for segment in hotel.get("segments", []):
            hotel_name = segment.get("recommend_hotel_name", "")
            if hotel_name:
                result["hotels"].append({
                    "name": hotel_name,
                    "check_in": segment.get("check_in", ""),
                    "check_in_time": segment.get("check_in_time", ""),
                    "check_out": segment.get("check_out", ""),
                    "check_out_time": segment.get("check_out_time", ""),
                    "segment_name": segment.get("segment_name", ""),
                })

    # --- Attractions (segment-based structure like hotel) ---
    attraction = agent_outputs.get("attraction_agent", {})
    if attraction and not attraction.get("skipped"):
        for segment in attraction.get("segments", []):
            seg_name = segment.get("segment_name", "")
            for attr in segment.get("attractions", []):
                attr_name = attr.get("name", "")
                if attr_name:
                    attr_entry = {
                        "name": attr_name,
                        "suggested_duration_minutes": attr.get("suggested_duration_minutes", 60),
                        "must_visit": attr.get("must_visit", False),
                        "segment_name": seg_name,
                        "includes": attr.get("includes", []),
                        "notes": attr.get("notes", ""),
                        "estimated_entrance_fee": attr.get("estimated_entrance_fee", {"total": 0, "note": ""}),
                    }
                    # Pass through pre-resolved placeId from Attraction Agent
                    if attr.get("placeId"):
                        attr_entry["placeId"] = attr["placeId"]
                    result["attractions"].append(attr_entry)

    return result


# ============================================================================
# STEP 2: Resolve place names to DB records
# ============================================================================

async def _resolve_single_place(
    name: str,
    location_bias: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """
    Resolve a single place name:
    1. Google Text Search → get PlaceId
    2. GET /api/place/{placeId} → .NET auto-ensures (fetches from Google API if not in DB)
    """
    logger.info(f"[resolve] Resolving: '{name}'")

    # Step 1: Text Search → PlaceId
    try:
        search_results = await places_text_search_id_only.ainvoke({
            "query": name,
            "location_bias": location_bias or "",
        })
    except Exception as e:
        logger.error(f"[resolve] Text search failed for '{name}': {e}")
        return None

    if not search_results or not isinstance(search_results, list) or len(search_results) == 0:
        logger.warning(f"[resolve] No results for '{name}'")
        return None

    if isinstance(search_results[0], dict) and "error" in search_results[0]:
        logger.error(f"[resolve] Search error for '{name}': {search_results[0]['error']}")
        return None

    place_id = search_results[0].get("place_id", "")
    if not place_id:
        logger.warning(f"[resolve] No PlaceId for '{name}'")
        return None

    logger.info(f"[resolve] Found PlaceId: {place_id} for '{name}'")

    # Step 2: GET /api/place/{placeId} → .NET auto-ensures
    try:
        db_result = await get_place_from_db.ainvoke({"place_id": place_id})
    except Exception as e:
        logger.error(f"[resolve] DB lookup failed for '{name}' (placeId={place_id}): {e}")
        return None

    if isinstance(db_result, dict) and db_result.get("success"):
        place_data = db_result.get("data", {})
        place_data["_resolved_name"] = name
        logger.info(f"[resolve] Resolved: '{name}' → {place_data.get('title', 'unknown')}")
        return place_data

    logger.warning(f"[resolve] Could not resolve '{name}' (placeId={place_id})")
    return None

async def resolve_all_places(
    place_names: dict[str, list[dict]],
    location_bias: Optional[str] = None,
    max_concurrent: int = 5,
) -> dict[str, list[dict]]:
    """
    Resolve all extracted place names to DB records with location + openHours.
    Uses a SINGLE asyncio.gather() with Semaphore to resolve ALL places concurrently
    while limiting to max_concurrent simultaneous resolutions.
    
    For attractions with a pre-resolved placeId (from Attraction Agent), skips textSearch
    and directly fetches from DB via get_place_from_db(placeId).
    
    Returns same structure as input but each item gets a 'resolved' key with full Place data.
    """
    import asyncio

    resolved = {"airports": [], "hotels": [], "attractions": []}
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _resolve_with_limit(name: str) -> Optional[dict]:
        async with semaphore:
            return await _resolve_single_place(name, location_bias)

    async def _resolve_by_place_id(place_id: str, name: str) -> Optional[dict]:
        """Resolve directly by placeId (skip textSearch)."""
        async with semaphore:
            logger.info(f"[resolve] Pre-resolved: '{name}' → placeId={place_id}")
            try:
                db_result = await get_place_from_db.ainvoke({"place_id": place_id})
                if isinstance(db_result, dict) and db_result.get("success"):
                    place_data = db_result.get("data", {})
                    place_data["_resolved_name"] = name
                    return place_data
            except Exception as e:
                logger.error(f"[resolve] DB lookup failed for pre-resolved '{name}' (placeId={place_id}): {e}")
            return None

    # --- Deduplicate airports (same airport may appear as outbound_arrival + return_departure) ---
    unique_airport_names: list[str] = []
    seen_airports: set[str] = set()
    for airport_info in place_names.get("airports", []):
        name = airport_info["name"]
        if name not in seen_airports:
            seen_airports.add(name)
            unique_airport_names.append(name)

    hotels_list = place_names.get("hotels", [])
    attractions_list = place_names.get("attractions", [])

    # --- Build ALL tasks and gather in one shot ---
    airport_tasks = [_resolve_with_limit(name) for name in unique_airport_names]
    hotel_tasks = [_resolve_with_limit(h["name"]) for h in hotels_list]

    # Attractions: use pre-resolved placeId if available, otherwise textSearch
    attraction_tasks = []
    for a in attractions_list:
        if a.get("placeId"):
            attraction_tasks.append(_resolve_by_place_id(a["placeId"], a["name"]))
        else:
            attraction_tasks.append(_resolve_with_limit(a["name"]))

    all_tasks = airport_tasks + hotel_tasks + attraction_tasks
    all_results = await asyncio.gather(*all_tasks) if all_tasks else []

    # --- Split results back by index ---
    ap_count = len(airport_tasks)
    ht_count = len(hotel_tasks)

    airport_results = all_results[:ap_count]
    hotel_results = all_results[ap_count:ap_count + ht_count]
    attraction_results = all_results[ap_count + ht_count:]

    # --- Map airport results (reuse cache for duplicates) ---
    airport_cache = dict(zip(unique_airport_names, airport_results))
    for airport_info in place_names.get("airports", []):
        name = airport_info["name"]
        resolved["airports"].append({**airport_info, "resolved": airport_cache.get(name)})

    for hotel_info, place_data in zip(hotels_list, hotel_results):
        resolved["hotels"].append({**hotel_info, "resolved": place_data})

    for attr_info, place_data in zip(attractions_list, attraction_results):
        resolved["attractions"].append({**attr_info, "resolved": place_data})

    return resolved


import re

def _parse_time_str(time_str: str) -> int:
    """
    Parse a time string to minutes since midnight.
    
    Handles formats:
        - "08:00", "17:30"          (24-hour)
        - "7:30 AM", "11:30 PM"    (12-hour with AM/PM)
        - "7 AM", "5 PM"           (12-hour without minutes)
        - "11\u202fAM"              (narrow no-break space)
    """
    s = time_str.strip()
    # Normalize unicode spaces
    s = s.replace('\u202f', ' ').replace('\u00a0', ' ').strip()
    
    # Detect AM/PM
    is_pm = False
    is_am = False
    upper = s.upper()
    if 'PM' in upper:
        is_pm = True
        s = re.sub(r'[APap][Mm]', '', s).strip()
    elif 'AM' in upper:
        is_am = True
        s = re.sub(r'[APap][Mm]', '', s).strip()
    
    # Parse hours and minutes
    parts = s.split(':')
    hours = int(parts[0].strip())
    minutes = int(parts[1].strip()) if len(parts) > 1 else 0
    
    # Convert 12-hour to 24-hour
    if is_pm and hours != 12:
        hours += 12
    elif is_am and hours == 12:
        hours = 0
    
    return hours * 60 + minutes


def _parse_time_range(range_str: str) -> Optional[tuple[int, int]]:
    """
    Parse a single time range string.
    
    Handles:
        - "08:00-17:00"            (24-hour, hyphen)
        - "7:30–11:30 AM"          (12-hour, en-dash, shared AM/PM)
        - "7:30 AM–5 PM"           (12-hour, en-dash, separate AM/PM)
        - "Closed"                 → None
        - "Open 24 hours"          → (0, 1440)
    """
    s = range_str.strip()
    s_lower = s.lower()
    
    if s_lower in ('closed', ''):
        return None
    
    if 'open 24' in s_lower or '24 hours' in s_lower:
        return (0, 1440)
    
    # Normalize separators: en-dash (–), em-dash (—), hyphen-minus (-)
    s = s.replace('–', '-').replace('—', '-')
    
    parts = s.split('-')
    if len(parts) != 2:
        return None
    
    open_str = parts[0].strip()
    close_str = parts[1].strip()
    
    # Handle shared AM/PM: "7:30–11:30 AM" → open="7:30", close="11:30 AM"
    # The period (AM/PM) is only on the close part
    # If open part has no AM/PM, inherit from close part
    close_upper = close_str.upper().replace('\u202f', ' ').replace('\u00a0', ' ')
    open_upper = open_str.upper().replace('\u202f', ' ').replace('\u00a0', ' ')
    
    has_period_in_open = 'AM' in open_upper or 'PM' in open_upper
    has_period_in_close = 'AM' in close_upper or 'PM' in close_upper
    
    if not has_period_in_open and has_period_in_close:
        # Inherit period from close → append to open
        period = 'AM' if 'AM' in close_upper else 'PM'
        open_str = open_str + ' ' + period
    
    try:
        open_min = _parse_time_str(open_str)
        close_min = _parse_time_str(close_str)
        if close_min > open_min:
            return (open_min, close_min)
    except (ValueError, IndexError):
        pass
    
    return None


def parse_open_hours_to_time_window(
    open_hours: dict[str, list[str]],
    day_name: str,
) -> Optional[tuple[int, int]]:
    """
    Convert openHours for a specific day to a VRP time window.
    
    Handles DB formats:
        - {"monday": ["7:30–11:30\u202fAM"]}
        - {"monday": ["7:30–11\u202fAM", "1:30–5\u202fPM"]}  → merged to widest
        - {"monday": ["Closed"]}
        - {"monday": ["Open 24 hours"]}
        - {"monday": ["08:00-17:00"]}  (24-hour, from resolve_place_details)
        
    Returns:
        (earliest_minutes, latest_minutes) or None if closed that day.
    """
    if not open_hours:
        return (480, 1320)  # Default: 08:00-22:00

    hours_list = open_hours.get(day_name, [])

    if not hours_list:
        # No entry for this day
        all_empty = all(len(v) == 0 for v in open_hours.values())
        if all_empty:
            return (480, 1320)  # All empty → default open
        return None  # Other days have data but this one doesn't → closed

    # Check for "Closed" or "Open 24 hours" as standalone entry
    if len(hours_list) == 1:
        single = hours_list[0].strip().lower()
        if single == 'closed':
            return None
        if 'open 24' in single or '24 hours' in single:
            return (0, 1440)

    # Parse all time ranges and find the widest window
    earliest = 1440
    latest = 0
    any_parsed = False
    
    for time_range in hours_list:
        result = _parse_time_range(time_range)
        if result is not None:
            earliest = min(earliest, result[0])
            latest = max(latest, result[1])
            any_parsed = True

    if not any_parsed or earliest >= latest:
        return (480, 1080)  # Fallback

    return (earliest, latest)


# ============================================================================
# STEP 4: Build VRP locations list
# ============================================================================

def _get_location_coords(place_data: Optional[dict]) -> Optional[dict[str, float]]:
    """Extract lat/lng from resolved place data."""
    if not place_data:
        return None
    location = place_data.get("location", {})
    coords = location.get("coordinates", [])
    if len(coords) >= 2:
        # GeoJSON: [lng, lat]
        return {"lat": coords[1], "lng": coords[0]}
    return None


def _parse_hub_time(time_str: str) -> int:
    """Parse transport hub time like '09:00' or '22:00 -1' to minutes since midnight.
    Strips day offset suffix (-1, +1) since VRP operates within each day."""
    s = time_str.strip().split()[0]  # Remove day offset suffix
    parts = s.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _flight_time_to_minutes(time_str: str) -> int:
    """Convert flight time like '09:00' to minutes since midnight."""
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def build_vrp_locations(
    resolved_places: dict[str, list[dict]],
    plan_context: dict[str, Any],
    flight_data: dict[str, Any],
    attraction_segments: list[dict] | None = None,
) -> list[dict]:
    """
    Build the locations list expected by solve_vrp().
    
    All day indices are 0-based (day 0 = first day, day 1 = second day, etc.).
    
    Maps:
    - Airports → outbound/return locations
    - Hotels → hotel locations with day/checkin/checkout
    - Attractions → attraction nodes (may split into multiple nodes if openHours differ per day)
    - Mobility plan → auxiliary nodes (midday rest, souvenir shopping)
    """
    locations = []
    
    start_date_str = plan_context.get("start_date", "")
    num_days = plan_context.get("num_days", 1)
    travel_by = plan_context.get("travel_by", "flight")
    mobility_plan = plan_context.get("mobility_plan") or {}

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else datetime.now()
    
    # Build day→weekday mapping (0-based)
    day_weekday_names = []  # day_weekday_names[0] = weekday name for day 0
    for d in range(num_days):
        day_date = start_date + timedelta(days=d)
        day_weekday_names.append(WEEKDAY_NAMES[day_date.weekday()])

    # Luggage logistics only needed for flight (airports have separate luggage drop/pick)
    is_flight = travel_by == "flight"
    needs_luggage_drop = is_flight
    needs_luggage_pickup = is_flight

    # --- Outbound (arrival airport/station) ---
    outbound_arrival = None
    for ap in resolved_places.get("airports", []):
        if ap.get("role") == "outbound_arrival":
            outbound_arrival = ap
            break
    
    if outbound_arrival:
        coords = _get_location_coords(outbound_arrival.get("resolved"))
        arrival_time = outbound_arrival.get("time", "09:00")
        if is_flight:
            arrival_minutes = _flight_time_to_minutes(arrival_time)
        else:
            arrival_minutes = _parse_hub_time(arrival_time)
        
        locations.append({
            "type": "outbound",
            "name": outbound_arrival.get("resolved", {}).get("title", outbound_arrival["name"]),
            "location": coords or {"lat": 0, "lng": 0},
            "time_window": (arrival_minutes, arrival_minutes),
            "drop_luggage": needs_luggage_drop,
        })

    # --- Return (departure airport/station) ---
    return_departure = None
    for ap in resolved_places.get("airports", []):
        if ap.get("role") == "return_departure":
            return_departure = ap
            break

    if return_departure:
        coords = _get_location_coords(return_departure.get("resolved"))
        dep_time = return_departure.get("time", "16:50")
        if is_flight:
            dep_minutes = _flight_time_to_minutes(dep_time)
            # For flights, arrive 2h early
            arrival_at_return = max(480, dep_minutes - 120)
        else:
            dep_minutes = _parse_hub_time(dep_time)
            # For non-flight, arrive 30min early
            arrival_at_return = max(480, dep_minutes - 30)
        
        locations.append({
            "type": "return",
            "name": return_departure.get("resolved", {}).get("title", return_departure["name"]),
            "location": coords or {"lat": 0, "lng": 0},
            "time_window": (arrival_at_return, dep_minutes),
            "pickup_luggage": needs_luggage_pickup,
        })

    # --- Hotels (one node per night, with optional midday rest) ---
    # midday_rest_days is 0-based from mobility_plan
    midday_rest_days = []
    if isinstance(mobility_plan, dict):
        midday_rest_days = mobility_plan.get("midday_rest_days") or []
    
    for hotel_info in resolved_places.get("hotels", []):
        coords = _get_location_coords(hotel_info.get("resolved"))
        if not coords:
            continue
        
        hotel_name = hotel_info.get("resolved", {}).get("title", hotel_info["name"])
        check_in_str = hotel_info.get("check_in", "")
        check_out_str = hotel_info.get("check_out", "")
        
        if check_in_str and check_out_str:
            try:
                ci = datetime.strptime(check_in_str, "%Y-%m-%d")
                co = datetime.strptime(check_out_str, "%Y-%m-%d")
                num_nights = (co - ci).days
            except ValueError:
                num_nights = max(num_days - 1, 1)
        else:
            num_nights = max(num_days - 1, 1)
        
        for night in range(num_nights):
            hotel_day = night  # 0-based day index
            hotel_node = {
                "type": "hotel",
                "name": hotel_name,
                "location": coords,
                "day": hotel_day,
                "checkin_time": (840, 1440),   # 14:00 - 24:00
                "checkout_time": (480, 540),   # 08:00 - 09:00
            }
            
            # Add midday rest if this day is in midday_rest_days (0-based)
            if hotel_day in midday_rest_days:
                # Determine if this is check-in day (first night at this hotel)
                # vs already staying (came back from previous night at same hotel)
                is_checkin_day = (
                    night == 0  # First night ever = always check-in
                    or hotel_name != hotel_info.get("resolved", {}).get("title", hotel_info["name"])
                    # For multi-hotel trips: would need to compare with prev hotel
                )
                if is_checkin_day:
                    # Check-in day: can't enter room until check-in time (14:00+)
                    hotel_node["break_time_window"] = (840, 900)   # 14:00 - 15:00
                    hotel_node["break_duration"] = 120
                else:
                    # Already staying: can return to room anytime
                    hotel_node["break_time_window"] = (720, 840)   # 12:00 - 14:00
                    hotel_node["break_duration"] = 120

            locations.append(hotel_node)

    # --- Attractions (with per-day time window splitting + allowed_days) ---
    disjunction_group_counter = 0

    # Build segment_name → allowed_days (0-indexed) mapping
    segment_days_map: dict[str, list[int]] = {}
    for seg in (attraction_segments or []):
        seg_name = seg.get("segment_name", "")
        # segments.days is 1-indexed → convert to 0-indexed
        seg_days = [d - 1 for d in seg.get("days", []) if isinstance(d, int)]
        if seg_name:
            segment_days_map[seg_name] = seg_days
    logger.info(f"[build_vrp] Segment→days map: {segment_days_map}")
    
    for attr_info in resolved_places.get("attractions", []):
        resolved = attr_info.get("resolved")
        coords = _get_location_coords(resolved)
        if not coords:
            logger.warning(f"[build_vrp] Skipping attraction '{attr_info['name']}' — no coordinates")
            continue

        duration = attr_info.get("suggested_duration_minutes", 60)
        is_must_visit = attr_info.get("must_visit", False)
        open_hours = resolved.get("openHours", {}) if resolved else {}
        attr_name = resolved.get("title", attr_info["name"]) if resolved else attr_info["name"]

        # Group trip days by their time window
        tw_groups: dict[tuple[int, int], list[int]] = {}  # {(open, close): [day_indices]}
        closed_day_indices: list[int] = []
        
        for day_idx in range(num_days):
            day_name = day_weekday_names[day_idx]
            tw = parse_open_hours_to_time_window(open_hours, day_name)
            if tw is None:
                closed_day_indices.append(day_idx)
            else:
                tw_groups.setdefault(tw, []).append(day_idx)

        if not tw_groups:
            # All days closed or no openHours → use default
            tw_groups[(480, 1320)] = list(range(num_days))
            closed_day_indices = []

        if len(tw_groups) == 1:
            # All open days have the same time window → single node
            # Determine allowed_days from segment mapping
            attr_segment = attr_info.get("segment_name", "")
            allowed_days = segment_days_map.get(attr_segment)

            node = {
                "type": "attraction",
                "name": attr_name,
                "location": coords,
                "time_window": tw,
                "duration": duration,
                "closed_days": closed_day_indices,
                "must_visit": is_must_visit,
            }
            if allowed_days is not None:
                node["allowed_days"] = allowed_days
            locations.append(node)
        else:
            # Multiple different time windows → split into separate nodes
            # Use _disjunction_group to mark them as mutually exclusive
            group_id = f"split_{disjunction_group_counter}"
            disjunction_group_counter += 1
            
            for tw, open_days in tw_groups.items():
                # This node is closed on all days NOT in open_days
                node_closed_days = [d for d in range(num_days) if d not in open_days]

                # Determine allowed_days from segment mapping
                attr_segment = attr_info.get("segment_name", "")
                allowed_days = segment_days_map.get(attr_segment)

                node = {
                    "type": "attraction",
                    "name": attr_name,
                    "location": coords,
                    "time_window": tw,
                    "duration": duration,
                    "closed_days": node_closed_days,
                    "must_visit": is_must_visit,
                    "_disjunction_group": group_id,
                }
                if allowed_days is not None:
                    node["allowed_days"] = allowed_days
                locations.append(node)
            logger.info(f"[build_vrp] Split '{attr_name}' into {len(tw_groups)} nodes (group={group_id})")

    # --- Souvenir Shopping (if requested, last day only) ---
    souvenir_shopping = False
    if isinstance(mobility_plan, dict):
        souvenir_shopping = mobility_plan.get("souvenir_shopping", False)
    
    if souvenir_shopping:
        locations.append({
            "type": "attraction",
            "name": "Souvenir Shopping",
            "location": {"lat": 0, "lng": 0},
            "time_window": (480, 1320),
            "duration": 90,
            "closed_days": list(range(0, num_days - 1)),  # Only allowed on the last day (0-based)
            "must_visit": False,
        })

    return locations


# ============================================================================
# STEP 5: Run full pipeline
# ============================================================================

async def run_itinerary_pipeline(
    agent_outputs: dict[str, Any],
    orchestrator_plan: dict[str, Any],
) -> dict[str, Any]:
    """
    Run the full itinerary pipeline:
    1. Extract place names from agent outputs
    2. Resolve all places (Text Search → .NET ensure → DB record)
    3. Build VRP locations list
    4. Run solve_vrp()
    5. Return VRP result
    """
    plan_context = orchestrator_plan.get("plan_context", {})
    flight_data = agent_outputs.get("flight_agent", {})
    
    # Get location bias from destination
    destination = plan_context.get("destination", "")
    location_bias = None  # Could compute from destination coords if needed
    
    logger.info("=" * 60)
    logger.info("🔧 [ITINERARY_BUILDER] Starting pipeline")

    # Step 1: Extract place names
    place_names = extract_place_names(agent_outputs, plan_context)
    logger.info(f"   Extracted: {len(place_names['airports'])} airports, "
                f"{len(place_names['hotels'])} hotels, "
                f"{len(place_names['attractions'])} attractions")

    # Step 2: Resolve all places
    logger.info("   Resolving places...")
    resolved = await resolve_all_places(place_names, location_bias)
    
    # Count resolved
    resolved_count = sum(
        1 for group in resolved.values()
        for item in group
        if item.get("resolved") is not None
    )
    total_count = sum(len(group) for group in resolved.values())
    logger.info(f"   Resolved: {resolved_count}/{total_count} places")

    # Step 3: Build VRP locations
    logger.info("   Building VRP locations...")
    vrp_locations = build_vrp_locations(
        resolved, plan_context, flight_data,
        attraction_segments=orchestrator_plan.get("attraction", {}).get("segments", []),
    )
    logger.info(f"   VRP locations: {vrp_locations}")

    if len(vrp_locations) < 2:
        logger.warning("   Not enough locations for VRP solver")
        return {
            "error": True,
            "message": "Not enough resolved places to build itinerary",
            "resolved_places": resolved,
            "vrp_locations": vrp_locations,
            "days": [],
            "dropped": [],
        }

    # Step 4: Run VRP solver
    logger.info("   Running VRP solver...")
    # Determine travel mode from plan_context
    local_transport = plan_context.get("local_transportation", "car")
    travel_mode = LOCAL_TRANSPORT_MAP.get(local_transport, "DRIVE")
    logger.info(f"   Travel mode: {local_transport} → {travel_mode}")
    
    vrp_result = await solve_vrp.ainvoke({
        "locations": vrp_locations,
        "use_api": True,
        "travel_mode": travel_mode,
        "time_limit_seconds": 5,
    })
    
    logger.nfo(f"   VRP result: error={vrp_result.get('error', False)}, "
                f"days={len(vrp_result.get('days', []))}, "
                f"dropped={len(vrp_result.get('dropped', []))}")

    # Step 5: Enrich result with metadata
    vrp_result["plan_context"] = {
        "start_date": plan_context.get("start_date", ""),
        "end_date": plan_context.get("end_date", ""),
        "num_days": plan_context.get("num_days", 0),
        "destination": plan_context.get("destination", ""),
    }
    vrp_result["resolved_places_count"] = resolved_count
    vrp_result["total_places_count"] = total_count

    logger.info("🔧 [ITINERARY_BUILDER] Pipeline completed")
    logger.info("=" * 60)

    return vrp_result
