"""
Itinerary Builder Service.

LLM-based pipeline that transforms agent outputs into LLM scheduling input:
1. Extract place names from flight/hotel/attraction agent outputs (reused)
2. Resolve each name to a Google Place ID via Text Search (reused)
3. Build distance matrix via Routes API
4. Format symmetric distance pairs + opening hours + soft constraints
5. Return structured data for LLM scheduling
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

from src.tools.maps_tools import places_text_search_id_only
from src.tools.dotnet_tools import get_place_from_db
from src.tools.itinerary_tools import _build_distance_matrix
from src.tools.maps_tools import LOCAL_TRANSPORT_MAP

logger = logging.getLogger(__name__)

# Day-of-week mapping: Python weekday() → OpenHours key
WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

def extract_place_names(
    agent_outputs: dict[str, Any],
    plan_context: dict[str, Any] | None = None,
) -> dict[str, list[dict]]:
    """
    Extract place names from flight/hotel/attraction agent outputs.
    Reads departure_logistics from mobility_plan for non-flight trips.
    Handles estimated entries from draft mode (estimated: true).
    """
    result = {"airports": [], "hotels": [], "attractions": []}
    plan_context = plan_context or {}

    # --- Flight ---
    flight = agent_outputs.get("flight_agent", {})
    if flight and not flight.get("skipped"):
        outbound = flight.get("recommend_outbound_flight", {})
        if outbound:
            result["airports"].append({
                "name": outbound.get("departure_airport_name", ""),
                "role": "outbound_departure",
                "time": outbound.get("departure_time", ""),
                "placeId": outbound.get("departure_airport_placeId"),
            })
            result["airports"].append({
                "name": outbound.get("arrival_airport_name", ""),
                "role": "outbound_arrival",
                "time": outbound.get("arrival_time", ""),
                "placeId": outbound.get("arrival_airport_placeId"),
            })

        return_flight = flight.get("recommend_return_flight", {})
        if return_flight:
            result["airports"].append({
                "name": return_flight.get("departure_airport_name", ""),
                "role": "return_departure",
                "time": return_flight.get("departure_time", ""),
                "placeId": return_flight.get("departure_airport_placeId"),
            })
            result["airports"].append({
                "name": return_flight.get("arrival_airport_name", ""),
                "role": "return_arrival",
                "time": return_flight.get("arrival_time", ""),
                "placeId": return_flight.get("arrival_airport_placeId"),
            })

    # --- Non-flight / Estimated flight: read from departure_logistics ---
    if not result["airports"]:
        mobility_plan = plan_context.get("mobility_plan") or {}
        dep_log = mobility_plan.get("departure_logistics") or {}
        ret_log = mobility_plan.get("return_logistics") or {}
        mode = dep_log.get("mode")

        if mode and mode != "flight":
            # Non-flight transport (coach/train/car — existing logic)
            hub_name = dep_log.get("hub_name")
            if hub_name:
                result["airports"].append({
                    "name": hub_name,
                    "role": "outbound_arrival",
                    "time": dep_log.get("ready_time") or dep_log.get("arrival_time", "07:00"),
                    "placeId": dep_log.get("hub_placeId"),
                })
            ret_hub = ret_log.get("hub_name")
            if ret_hub:
                result["airports"].append({
                    "name": ret_hub,
                    "role": "return_departure",
                    "time": ret_log.get("departure_time", "15:00"),
                    "placeId": ret_log.get("hub_placeId"),
                })

        elif mode == "flight" and dep_log.get("estimated"):
            # DRAFT MODE: Estimated flight — NOT resolved, just labels for LLM
            hub_name = dep_log.get("hub_name")
            if hub_name:
                result["airports"].append({
                    "name": hub_name,
                    "role": "outbound_arrival",
                    "time": dep_log.get("arrival_time", "09:00"),
                    "estimated": True,
                })
            ret_hub = ret_log.get("hub_name")
            if ret_hub:
                result["airports"].append({
                    "name": ret_hub,
                    "role": "return_departure",
                    "time": ret_log.get("start_time", "18:00"),
                    "estimated": True,
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
                    "placeId": segment.get("recommend_hotel_placeId"),
                })

    # --- Estimated hotel from segments (draft mode) ---
    if not result["hotels"]:
        mobility_plan = plan_context.get("mobility_plan") or {}
        segments = mobility_plan.get("segments", [])
        start_date = plan_context.get("start_date", "")
        for seg in segments:
            if not seg.get("hotel_nights"):
                continue
            hotel_area = seg.get("hotel_search_area", "")
            if not hotel_area:
                continue
            nights = seg["hotel_nights"]
            ci_date = _add_days(start_date, min(nights)) if start_date else ""
            co_date = _add_days(start_date, max(nights) + 1) if start_date else ""
            result["hotels"].append({
                "name": f"Khách sạn kv. {hotel_area}",
                "check_in": ci_date,
                "check_in_time": "14:00",
                "check_out": co_date,
                "check_out_time": "12:00",
                "segment_name": seg.get("segment_name", ""),
                "estimated": True,
                "hotel_area": hotel_area,
            })

    # --- Attractions ---
    attraction = agent_outputs.get("attraction_agent", {})
    if attraction and not attraction.get("skipped"):
        for segment in attraction.get("segments", []):
            seg_name = segment.get("segment_name", "")
            for attr in segment.get("attractions", []):
                attr_name = attr.get("name", "")
                if attr_name:
                    attr_entry = {
                        "name": attr_name,
                        "must_visit": attr.get("must_visit", False),
                        "segment_name": seg_name,
                        "includes": attr.get("includes", []),
                        "notes": attr.get("notes", ""),
                        "estimated_entrance_fee": attr.get("estimated_entrance_fee", {"total": 0, "note": ""}),
                    }
                    if attr.get("placeId"):
                        attr_entry["placeId"] = attr["placeId"]
                    result["attractions"].append(attr_entry)

    return result


def _add_days(date_str: str, days: int) -> str:
    """Add days to a date string (YYYY-MM-DD)."""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return (dt + timedelta(days=days)).strftime("%Y-%m-%d")
    except ValueError:
        return ""


async def _resolve_single_place(
    name: str,
    location_bias: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Resolve a single place name via Text Search → DB lookup."""
    logger.info(f"[resolve] Resolving: '{name}'")

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
        return None

    logger.info(f"[resolve] Found PlaceId: {place_id} for '{name}'")

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
    """Resolve all extracted place names. Uses pre-resolved placeIds when available."""
    resolved = {"airports": [], "hotels": [], "attractions": []}
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _resolve_with_limit(name: str) -> Optional[dict]:
        async with semaphore:
            return await _resolve_single_place(name, location_bias)

    async def _resolve_by_place_id(place_id: str, name: str) -> Optional[dict]:
        async with semaphore:
            logger.info(f"[resolve] Pre-resolved: '{name}' → placeId={place_id}")
            try:
                db_result = await get_place_from_db.ainvoke({"place_id": place_id})
                if isinstance(db_result, dict) and db_result.get("success"):
                    place_data = db_result.get("data", {})
                    place_data["_resolved_name"] = name
                    return place_data
            except Exception as e:
                logger.error(f"[resolve] DB lookup failed for pre-resolved '{name}': {e}")
            return None

    # Deduplicate airports — skip estimated entries
    unique_airport_names: list[str] = []
    seen_airports: set[str] = set()
    airport_place_ids: dict[str, str] = {}  # name → placeId
    estimated_airports: list[dict] = []
    for airport_info in place_names.get("airports", []):
        if airport_info.get("estimated"):
            # Draft mode: don't resolve, pass through as-is
            estimated_airports.append(airport_info)
            continue
        name = airport_info["name"]
        if name not in seen_airports:
            seen_airports.add(name)
            unique_airport_names.append(name)
            if airport_info.get("placeId"):
                airport_place_ids[name] = airport_info["placeId"]

    # Filter hotels — skip estimated entries
    hotels_to_resolve = [h for h in place_names.get("hotels", []) if not h.get("estimated")]
    estimated_hotels = [h for h in place_names.get("hotels", []) if h.get("estimated")]
    attractions_list = place_names.get("attractions", [])

    # Build tasks — use pre-resolved placeId when available
    airport_tasks = [
        _resolve_by_place_id(airport_place_ids[n], n) if n in airport_place_ids
        else _resolve_with_limit(n)
        for n in unique_airport_names
    ]
    hotel_tasks = [
        _resolve_by_place_id(h["placeId"], h["name"]) if h.get("placeId")
        else _resolve_with_limit(h["name"])
        for h in hotels_to_resolve
    ]
    attraction_tasks = [
        _resolve_by_place_id(a["placeId"], a["name"]) if a.get("placeId")
        else _resolve_with_limit(a["name"])
        for a in attractions_list
    ]

    all_tasks = airport_tasks + hotel_tasks + attraction_tasks
    all_results = await asyncio.gather(*all_tasks) if all_tasks else []

    ap_count = len(airport_tasks)
    ht_count = len(hotel_tasks)

    airport_results = all_results[:ap_count]
    hotel_results = all_results[ap_count:ap_count + ht_count]
    attraction_results = all_results[ap_count + ht_count:]

    airport_cache = dict(zip(unique_airport_names, airport_results))
    # Add resolved airports
    for airport_info in place_names.get("airports", []):
        if airport_info.get("estimated"):
            # Pass through estimated entries with resolved=None
            resolved["airports"].append({**airport_info, "resolved": None})
        else:
            name = airport_info["name"]
            resolved["airports"].append({**airport_info, "resolved": airport_cache.get(name)})

    # Add resolved hotels + estimated hotels
    for hotel_info, place_data in zip(hotels_to_resolve, hotel_results):
        resolved["hotels"].append({**hotel_info, "resolved": place_data})
    for hotel_info in estimated_hotels:
        resolved["hotels"].append({**hotel_info, "resolved": None})

    for attr_info, place_data in zip(attractions_list, attraction_results):
        resolved["attractions"].append({**attr_info, "resolved": place_data})

    return resolved





def _get_location_coords(place_data: Optional[dict]) -> Optional[dict[str, float]]:
    """Extract lat/lng from resolved place data."""
    if not place_data:
        return None
    location = place_data.get("location", {})
    coords = location.get("coordinates", [])
    if len(coords) >= 2:
        return {"lat": coords[1], "lng": coords[0]}
    return None





def _parse_hotel_time(time_str: str) -> str:
    """Convert hotel API time format to 24h format.
    
    Examples:
        '02:00 PM' → '14:00'
        '12:00 PM' → '12:00'
        '12:00 AM' → '00:00'
        '14:00'    → '14:00' (already 24h)
    """
    if not time_str:
        return ""
    s = time_str.strip().upper()
    
    # Already 24h format (no AM/PM)
    if "AM" not in s and "PM" not in s:
        return time_str.strip()
    
    # Parse "HH:MM AM/PM"
    is_pm = "PM" in s
    s = s.replace("AM", "").replace("PM", "").strip()
    parts = s.split(":")
    if len(parts) != 2:
        return time_str.strip()
    
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        
        if is_pm and hour != 12:
            hour += 12
        elif not is_pm and hour == 12:
            hour = 0
        
        return f"{hour:02d}:{minute:02d}"
    except ValueError:
        return time_str.strip()


# ============================================================================
# STEP 3: Build location list for distance matrix
# ============================================================================

def build_location_list(
    resolved_places: dict[str, list[dict]],
) -> list[dict]:
    """
    Build a flat list of unique locations for distance matrix calculation.
    Returns list of dicts with: name, lat, lng, type.
    """
    locations = []
    seen_coords = set()

    def _add_if_unique(name, lat, lng, loc_type):
        coord_key = (round(lat, 5), round(lng, 5))
        if coord_key not in seen_coords:
            seen_coords.add(coord_key)
            locations.append({"name": name, "lat": lat, "lng": lng, "type": loc_type})

    # --- Transport hubs: only DESTINATION-side (outbound_arrival, return_departure) ---
    # Origin-side hubs (outbound_departure, return_arrival) are in a different city
    # and would produce nonsensical route matrix distances with local travel mode.
    destination_roles = {"outbound_arrival", "return_departure"}
    for ap in resolved_places.get("airports", []):
        role = ap.get("role", "")
        if role not in destination_roles:
            continue
        coords = _get_location_coords(ap.get("resolved"))
        if coords:
            hub_name = (ap.get("resolved") or {}).get("title", ap["name"])
            _add_if_unique(hub_name, coords["lat"], coords["lng"], role)

    # --- Hotels ---
    for hotel_info in resolved_places.get("hotels", []):
        coords = _get_location_coords(hotel_info.get("resolved"))
        if coords:
            hotel_name = (hotel_info.get("resolved") or {}).get("title", hotel_info["name"])
            _add_if_unique(hotel_name, coords["lat"], coords["lng"], "hotel")

    # --- Attractions ---
    for attr_info in resolved_places.get("attractions", []):
        resolved = attr_info.get("resolved")
        coords = _get_location_coords(resolved)
        if coords:
            attr_name = resolved.get("title", attr_info["name"]) if resolved else attr_info["name"]
            _add_if_unique(attr_name, coords["lat"], coords["lng"], "attraction")

    return locations


# ============================================================================
# STEP 4: Build symmetric distance pairs
# ============================================================================

def build_symmetric_distance_pairs(
    locations: list[dict],
    distance_matrix: list[list[int]],
) -> list[dict]:
    """
    Convert NxN distance matrix to compact symmetric list (A↔B).
    Only outputs upper triangle (i < j). Raw travel times only —
    the LLM adds flexible buffer itself for more natural scheduling.
    """
    pairs = []
    n = len(locations)

    for i in range(n):
        for j in range(i + 1, n):
            raw_avg = (distance_matrix[i][j] + distance_matrix[j][i]) // 2
            pairs.append({
                "from": locations[i]["name"],
                "to": locations[j]["name"],
                "raw_minutes": raw_avg,
            })

    return pairs


# ============================================================================
# STEP 5: Build attractions info with opening hours
# ============================================================================

def build_attractions_info(
    resolved_places: dict[str, list[dict]],
    plan_context: dict[str, Any],
) -> list[dict]:
    """
    Extract per-attraction opening hours for each trip day.
    """
    start_date_str = plan_context.get("start_date", "")
    num_days = plan_context.get("num_days", 1)
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else datetime.now()

    day_weekday_names = []
    for d in range(num_days):
        day_date = start_date + timedelta(days=d)
        day_weekday_names.append(WEEKDAY_NAMES[day_date.weekday()])

    attractions_info = []
    for attr_info in resolved_places.get("attractions", []):
        resolved = attr_info.get("resolved")
        if not resolved:
            continue

        attr_name = resolved.get("title", attr_info["name"])
        open_hours = resolved.get("openHours", {})
        is_must_visit = attr_info.get("must_visit", False)
        segment_name = attr_info.get("segment_name", "")

        hours_by_day = {}
        for day_idx in range(num_days):
            day_name = day_weekday_names[day_idx]
            day_label = f"day_{day_idx + 1} ({day_name[:3].capitalize()})"

            if not open_hours:
                hours_by_day[day_label] = "08:00-22:00 (assumed)"
                continue

            hours_list = open_hours.get(day_name, [])
            if not hours_list:
                all_empty = all(len(v) == 0 for v in open_hours.values())
                hours_by_day[day_label] = "08:00-22:00 (assumed)" if all_empty else "Closed"
                continue

            if len(hours_list) == 1:
                single = hours_list[0].strip().lower()
                if single == "closed":
                    hours_by_day[day_label] = "Closed"
                    continue
                if "open 24" in single or "24 hours" in single:
                    hours_by_day[day_label] = "Open 24 hours"
                    continue

            hours_by_day[day_label] = ", ".join(hours_list)

        attractions_info.append({
            "name": attr_name,
            "opening_hours": hours_by_day,
            "must_visit": is_must_visit,
            "segment_name": segment_name,
            "includes": attr_info.get("includes", []),
            "notes": attr_info.get("notes", ""),
            "estimated_entrance_fee": attr_info.get("estimated_entrance_fee", {"total": 0, "note": ""}),
        })

    return attractions_info


# ============================================================================
# STEP 6: Build soft constraints for LLM
# ============================================================================

def build_schedule_constraints(
    resolved_places: dict[str, list[dict]],
    plan_context: dict[str, Any],
    flight_data: dict[str, Any],
) -> dict:
    """
    Build soft constraints for the LLM scheduler.

    Only hard constraints:
    - day_0_arrival: where and when the traveler arrives on day 0
    - last_day_deadline: when the last day must end (for flight or transport)
    - hotels: which hotel for which nights
    - luggage: whether luggage drop/pickup is needed (flight only)

    The LLM decides daily start/end times, checkout time, etc.
    """
    num_days = plan_context.get("num_days", 1)
    start_date_str = plan_context.get("start_date", "")
    mobility_plan = plan_context.get("mobility_plan") or {}

    constraints = {
        "num_days": num_days,
        "start_date": start_date_str,
        "pace": plan_context.get("pace", "moderate"),
        "local_transportation": plan_context.get("local_transportation", "car"),
    }

    # --- Day 0 arrival info ---
    dep_log = mobility_plan.get("departure_logistics") or {}
    dep_mode = dep_log.get("mode", "")

    if dep_mode == "flight" and flight_data and not flight_data.get("skipped"):
        outbound = flight_data.get("recommend_outbound_flight", {})
        if outbound:
            constraints["day_0_arrival"] = {
                "location": outbound.get("arrival_airport_name", "Airport"),
                "arrival_time": outbound.get("arrival_time", "09:00"),
                "flight_number": outbound.get("flight_number", ""),
                "airline": outbound.get("airline", ""),
                "departure_airport": outbound.get("departure_airport_name", ""),
                "departure_time": outbound.get("departure_time", ""),
                "note": "Arrive by flight.",
            }
    elif dep_mode == "flight" and dep_log.get("estimated"):
        # DRAFT MODE: Use Macro Planning estimates
        constraints["day_0_arrival"] = {
            "location": dep_log.get("hub_name", "Airport"),
            "departure_time": dep_log.get("start_time", ""),
            "arrival_time": dep_log.get("arrival_time", "09:00"),
            "note": dep_log.get("note", "Estimated flight arrival"),
        }
    elif dep_mode in ("coach", "train") and dep_log.get("hub_name"):
        # Use resolved title from resolved_places (matches distance matrix name)
        hub_resolved_name = dep_log.get("hub_name", "")
        for ap in resolved_places.get("airports", []):
            if ap.get("role") == "outbound_arrival" and ap.get("resolved"):
                hub_resolved_name = ap["resolved"].get("title", hub_resolved_name)
                break
        constraints["day_0_arrival"] = {
            "location": hub_resolved_name,
            "start_time": dep_log.get("start_time", ""),
            "arrival_time": dep_log.get("arrival_time", ""),
            "note": dep_log.get("note", f"Arrive by {dep_mode}"),
        }
    elif dep_mode in ("car", "motorbike"):
        constraints["day_0_arrival"] = {
            "start_time": dep_log.get("start_time", ""),
            "arrival_time": dep_log.get("arrival_time", ""),
            "note": dep_log.get("note", f"Self-drive from {plan_context.get('departure', '')}."),
        }
    # else: local trip, departure_logistics is null → no arrival constraint

    # --- Last day deadline ---
    ret_log = mobility_plan.get("return_logistics") or {}
    ret_mode = ret_log.get("mode", "")

    if ret_mode == "flight" and flight_data and not flight_data.get("skipped"):
        return_flight = flight_data.get("recommend_return_flight", {})
        if return_flight:
            dep_time = return_flight.get("departure_time", "")
            dep_airport = return_flight.get("departure_airport_name", "Airport")
            if dep_time:
                parts = dep_time.split(":")
                dep_minutes = int(parts[0]) * 60 + int(parts[1])
                # Must arrive at airport 2h before flight
                deadline_min = max(480, dep_minutes - 120)
                deadline_time = f"{deadline_min // 60:02d}:{deadline_min % 60:02d}"
                constraints["last_day_deadline"] = {
                    "location": dep_airport,
                    "deadline_time": deadline_time,
                    "flight_departure": dep_time,
                    "flight_number": return_flight.get("flight_number", ""),
                    "airline": return_flight.get("airline", ""),
                    "arrival_airport": return_flight.get("arrival_airport_name", ""),
                    "arrival_time": return_flight.get("arrival_time", ""),
                    "note": f"Must arrive at {dep_airport} by {deadline_time} (2h before {dep_time} flight).",
                }
    elif ret_mode == "flight" and ret_log.get("estimated"):
        # DRAFT MODE: Use Macro Planning estimates for return flight deadline
        ret_start = ret_log.get("start_time", "")
        if ret_start:
            parts = ret_start.split(":")
            start_min = int(parts[0]) * 60 + int(parts[1])
            deadline_min = max(480, start_min - 120)
            deadline_time = f"{deadline_min // 60:02d}:{deadline_min % 60:02d}"
            constraints["last_day_deadline"] = {
                "mode": "flight",
                "location": ret_log.get("hub_name", "Airport"),
                "deadline_time": deadline_time,
                "start_time": ret_start,
                "arrival_time": ret_log.get("arrival_time", ""),
                "note": f"Estimated return flight. Arrive at airport by {deadline_time}.",
            }
    elif ret_mode in ("coach", "train") and ret_log.get("hub_name"):
        # Use resolved title from resolved_places (matches distance matrix name)
        ret_hub_resolved_name = ret_log.get("hub_name", "")
        for ap in resolved_places.get("airports", []):
            if ap.get("role") == "return_departure" and ap.get("resolved"):
                ret_hub_resolved_name = ap["resolved"].get("title", ret_hub_resolved_name)
                break
        ret_start = ret_log.get("start_time", "")
        # 30-min buffer: arrive at hub 30 min before departure for boarding/tickets
        if ret_start:
            parts = ret_start.split(":")
            start_min = int(parts[0]) * 60 + int(parts[1])
            dl_min = max(0, start_min - 30)
            dl_time = f"{dl_min // 60:02d}:{dl_min % 60:02d}"
        else:
            dl_time = ""
        constraints["last_day_deadline"] = {
            "mode": ret_mode,
            "location": ret_hub_resolved_name,
            "deadline_time": dl_time,
            "start_time": ret_start,
            "arrival_time": ret_log.get("arrival_time", ""),
            "note": ret_log.get("note", f"Must arrive at {ret_hub_resolved_name} by {dl_time} (~30 min before {ret_start} {ret_mode})."),
        }
    elif ret_mode in ("car", "motorbike"):
        ret_start = ret_log.get("start_time", "")
        constraints["last_day_deadline"] = {
            "mode": ret_mode,
            "deadline_time": ret_start,  # exact time, no buffer needed
            "start_time": ret_start,
            "arrival_time": ret_log.get("arrival_time", ""),
            "note": ret_log.get("note", f"Self-drive return journey, depart at {ret_start}."),
        }
    # else: local trip → no hard deadline

    # --- Hotels per night (with actual times from API) ---
    hotels = resolved_places.get("hotels", [])
    hotel_schedule = []
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None

    for h in hotels:
        name = (h.get("resolved") or {}).get("title", h.get("name", "Hotel"))
        ci_date = h.get("check_in", "")
        co_date = h.get("check_out", "")

        # Parse check-in/check-out times from hotel agent (e.g., "02:00 PM")
        ci_time_raw = h.get("check_in_time", "")
        co_time_raw = h.get("check_out_time", "")
        ci_time = _parse_hotel_time(ci_time_raw) if ci_time_raw else "14:00"
        co_time = _parse_hotel_time(co_time_raw) if co_time_raw else "12:00"

        # Calculate 1-indexed day numbers for check-in and check-out
        ci_day_idx = None
        co_day_idx = None
        if start_date and ci_date:
            try:
                ci_day_idx = (datetime.strptime(ci_date, "%Y-%m-%d") - start_date).days + 1
            except ValueError:
                pass
        if start_date and co_date:
            try:
                co_day_idx = (datetime.strptime(co_date, "%Y-%m-%d") - start_date).days + 1
            except ValueError:
                pass

        hotel_entry = {
            "name": name,
            "check_in_date": ci_date,
            "check_out_date": co_date,
            "check_in_time": ci_time,
            "check_out_time": co_time,
            "segment_name": h.get("segment_name", ""),
        }
        if ci_day_idx is not None:
            hotel_entry["check_in_day"] = ci_day_idx
        if co_day_idx is not None:
            hotel_entry["check_out_day"] = co_day_idx
        hotel_schedule.append(hotel_entry)

    constraints["hotels"] = hotel_schedule
    
    if hotel_schedule:
        constraints["accommodation_context"] = {
            "type": "hotel",
            "note": "Travelers are staying at hotels. You MUST strictly respect check-in and check-out times provided in the `hotels` constraint. Resting is only possible after check-in."
        }
    else:
        constraints["accommodation_context"] = {
            "type": "home",
            "note": "Travelers are staying at their own home (or an unmanaged location). NO check-in or check-out is needed. They can return home to `rest` at literally ANY time they want."
        }

    # --- Luggage context (tells LLM whether luggage management is needed) ---
    local_transport = plan_context.get("local_transportation", "")
    if dep_mode == "flight" or dep_mode in ("coach", "train"):
        constraints["luggage_context"] = {
            "needs_luggage_management": True,
            "note": (
                "Travelers arrive with luggage at a transport hub. "
                "They need to drop luggage at hotel if arriving before check-in, "
                "or check-in directly if arriving after check-in time. "
                "On departure day, if they have time after checkout, they can store luggage and pick up later."
            ),
        }
    elif local_transport in ("car", "motorbike") or dep_mode in ("car", "motorbike"):
        constraints["luggage_context"] = {
            "needs_luggage_management": False,
            "note": "Self-drive: luggage stays in vehicle. No luggage_drop or luggage_pickup needed.",
        }
    else:
        constraints["luggage_context"] = {
            "needs_luggage_management": False,
            "note": "Local trip or simple transfer. No special luggage handling.",
        }

    # --- Mobility plan overview (context for LLM scheduler) ---
    overview = mobility_plan.get("overview", "")
    if overview:
        constraints["mobility_plan_overview"] = overview

    return constraints


# ============================================================================
# MAIN PIPELINE
# ============================================================================

async def run_itinerary_pipeline(
    agent_outputs: dict[str, Any],
    macro_plan: dict[str, Any],
    plan_context: dict[str, Any] = None,
    useAPI_RouteMatrix: bool = False,
) -> dict[str, Any]:
    """
    Run the itinerary pipeline:
    1. Extract place names
    2. Resolve all places
    3. Build location list & distance matrix
    4. Build attractions info with opening hours
    5. Build soft schedule constraints
    6. Return everything for LLM scheduling
    """
    # plan_context comes from current_plan (single source of truth)
    # Inject mobility_plan from macro_plan so internal functions can read it
    plan_context = dict(plan_context or {})
    mobility_plan = macro_plan.get("mobility_plan", {})
    if mobility_plan:
        plan_context["mobility_plan"] = mobility_plan
    flight_data = agent_outputs.get("flight_agent", {})

    logger.info("=" * 60)
    logger.info("🔧 [ITINERARY_BUILDER] Starting pipeline")

    # Step 1: Extract place names
    place_names = extract_place_names(agent_outputs, plan_context)
    logger.info(f"   Extracted: {len(place_names['airports'])} airports, "
                f"{len(place_names['hotels'])} hotels, "
                f"{len(place_names['attractions'])} attractions")

    # Step 2: Resolve all places
    logger.info("   Resolving places...")
    resolved = await resolve_all_places(place_names)

    resolved_count = sum(
        1 for group in resolved.values()
        for item in group
        if item.get("resolved") is not None
    )
    total_count = sum(len(group) for group in resolved.values())
    logger.info(f"   Resolved: {resolved_count}/{total_count} places")

    # Step 3: Build location list & distance matrix
    logger.info("   Building location list...")
    locations = build_location_list(resolved)
    logger.info(f"   Locations: {len(locations)} unique places")

    if len(locations) < 2:
        logger.warning("   Not enough locations for scheduling")
        return {
            "error": True,
            "message": "Not enough resolved places to build itinerary",
            "distance_pairs": [],
            "attractions_info": [],
            "schedule_constraints": {},
            "resolved_places": resolved,
        }

    logger.info("   Computing distance matrix...")
    local_transport = plan_context.get("local_transportation", "car")
    travel_mode = LOCAL_TRANSPORT_MAP.get(local_transport, "DRIVE")
    logger.info(f"   Travel mode: {local_transport} → {travel_mode}")

    raw_matrix = await _build_distance_matrix(locations, use_api=useAPI_RouteMatrix, travel_mode=travel_mode)
    distance_pairs = build_symmetric_distance_pairs(locations, raw_matrix)
    logger.info(f"   Distance pairs: {len(distance_pairs)} symmetric pairs")

    # Step 4: Build attractions info
    attractions_info = build_attractions_info(resolved, plan_context)
    logger.info(f"   Attractions info: {len(attractions_info)} with hours")

    # Step 5: Build schedule constraints
    schedule_constraints = build_schedule_constraints(resolved, plan_context, flight_data)

    result = {
        "error": False,
        "distance_pairs": distance_pairs,
        "attractions_info": attractions_info,
        "schedule_constraints": schedule_constraints,
        "resolved_places": resolved,
        "resolved_places_count": resolved_count,
        "total_places_count": total_count,
    }

    logger.info("🔧 [ITINERARY_BUILDER] Pipeline completed")
    logger.info("=" * 60)

    return result
