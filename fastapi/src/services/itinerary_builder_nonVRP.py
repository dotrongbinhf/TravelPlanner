"""
Itinerary Builder Service (Non-VRP version).

LLM-based pipeline that transforms agent outputs into LLM scheduling input:
1. Extract place names from flight/hotel/attraction agent outputs (reused)
2. Resolve each name to a Google Place ID via Text Search (reused)
3. Build distance matrix via Routes API
4. Format symmetric distance pairs + opening hours + soft constraints
5. Return structured data for LLM scheduling
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

# Reuse from original itinerary_builder
from src.services.itinerary_builder import (
    extract_place_names,
    resolve_all_places,
    parse_open_hours_to_time_window,
    WEEKDAY_NAMES,
    _get_location_coords,
    _parse_hub_time,
    _flight_time_to_minutes,
)

# Reuse distance matrix builder from itinerary_tools
from src.tools.itinerary_tools import _build_distance_matrix
from src.tools.maps_tools import LOCAL_TRANSPORT_MAP

logger = logging.getLogger(__name__)


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
            hub_name = ap.get("resolved", {}).get("title", ap["name"])
            _add_if_unique(hub_name, coords["lat"], coords["lng"], role)

    # --- Hotels ---
    for hotel_info in resolved_places.get("hotels", []):
        coords = _get_location_coords(hotel_info.get("resolved"))
        if coords:
            hotel_name = hotel_info.get("resolved", {}).get("title", hotel_info["name"])
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
        duration = attr_info.get("suggested_duration_minutes", 60)
        is_must_visit = attr_info.get("must_visit", False)
        segment_name = attr_info.get("segment_name", "")

        hours_by_day = {}
        for day_idx in range(num_days):
            day_name = day_weekday_names[day_idx]
            day_label = f"day_{day_idx} ({day_name[:3].capitalize()})"

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
            "suggested_duration_minutes": duration,
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
    travel_by = plan_context.get("travel_by", "flight")
    mobility_plan = plan_context.get("mobility_plan") or {}
    is_flight = travel_by == "flight"

    constraints = {
        "num_days": num_days,
        "start_date": start_date_str,
        "pace": plan_context.get("pace", "moderate"),
        "local_transportation": plan_context.get("local_transportation", "car"),
        "travel_by": travel_by,
    }

    # --- Day 0 arrival info ---
    if is_flight and flight_data and not flight_data.get("skipped"):
        outbound = flight_data.get("recommend_outbound_flight", {})
        if outbound:
            constraints["day_0_arrival"] = {
                "location": outbound.get("arrival_airport_name", "Airport"),
                "arrival_time": outbound.get("arrival_time", "09:00"),
                "note": "Arrive by flight. Need to drop luggage at hotel before exploring.",
            }
    else:
        transport_hubs = mobility_plan.get("transport_hubs") or {}
        if transport_hubs:
            constraints["day_0_arrival"] = {
                "location": transport_hubs.get("outbound_arrival", ""),
                "arrival_time": transport_hubs.get("outbound_arrival_time", ""),
                "ready_time": transport_hubs.get("outbound_ready_time", ""),
                "note": "Arrive by " + travel_by,
            }

    # --- Last day deadline ---
    if is_flight and flight_data and not flight_data.get("skipped"):
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
                    "note": f"Must arrive at {dep_airport} by {deadline_time} (2h before {dep_time} flight). Need to pick up luggage from hotel before heading to airport.",
                }
    else:
        transport_hubs = mobility_plan.get("transport_hubs") or {}
        return_dep_time = transport_hubs.get("return_departure_time", "")
        return_departure = transport_hubs.get("return_departure", "")
        if return_dep_time:
            constraints["last_day_deadline"] = {
                "location": return_departure,
                "deadline_time": return_dep_time,
                "note": f"Must be at {return_departure} by {return_dep_time} for the return journey.",
            }

    # --- Hotels per night (with actual times from API) ---
    hotels = resolved_places.get("hotels", [])
    hotel_schedule = []
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else None

    for h in hotels:
        name = h.get("resolved", {}).get("title", h.get("name", "Hotel"))
        ci_date = h.get("check_in", "")
        co_date = h.get("check_out", "")

        # Parse check-in/check-out times from hotel agent (e.g., "02:00 PM")
        ci_time_raw = h.get("check_in_time", "")
        co_time_raw = h.get("check_out_time", "")
        ci_time = _parse_hotel_time(ci_time_raw) if ci_time_raw else "14:00"
        co_time = _parse_hotel_time(co_time_raw) if co_time_raw else "12:00"

        # Calculate 0-indexed day numbers for check-in and check-out
        ci_day_idx = None
        co_day_idx = None
        if start_date and ci_date:
            try:
                ci_day_idx = (datetime.strptime(ci_date, "%Y-%m-%d") - start_date).days
            except ValueError:
                pass
        if start_date and co_date:
            try:
                co_day_idx = (datetime.strptime(co_date, "%Y-%m-%d") - start_date).days
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

    # --- Luggage logistics (flight only) ---
    if is_flight:
        constraints["luggage"] = {
            "drop_luggage": "Drop luggage at hotel before exploring on day 0 (hotel may allow luggage storage before check-in time)",
            "pick_up_luggage": "Pick up luggage from hotel before heading to airport on last day",
        }

    # --- Midday rest (SUGGESTION — Itinerary Agent decides based on actual schedule) ---
    midday_rest_days = mobility_plan.get("midday_rest_days")
    if midday_rest_days:
        constraints["midday_rest_days"] = midday_rest_days
        constraints["midday_rest_note"] = (
            "The Orchestrator SUGGESTS midday rest on these days, but YOU decide based on the actual schedule."
            "Skip midday rest if: the day starts late, the schedule is already short, or there's not enough time. "
            "Add midday rest if: travelers have young children/infants and started early, or the day is long and hot."
            "ONLY on the check-in day: room is available from check-in time, so rest MUST be AFTER check-in time."
        )

    # --- Souvenir shopping ---
    souvenir = mobility_plan.get("souvenir_shopping")
    if souvenir:
        constraints["souvenir_shopping"] = True

    # --- Mobility plan text ---
    plan_text = mobility_plan.get("plan", "")
    if plan_text:
        constraints["mobility_plan_description"] = plan_text

    return constraints


# ============================================================================
# MAIN PIPELINE
# ============================================================================

async def run_itinerary_pipeline_nonVRP(
    agent_outputs: dict[str, Any],
    orchestrator_plan: dict[str, Any],
    useAPI_RouteMatrix: bool = False,
) -> dict[str, Any]:
    """
    Run the non-VRP itinerary pipeline:
    1. Extract place names
    2. Resolve all places
    3. Build location list & distance matrix
    4. Build attractions info with opening hours
    5. Build soft schedule constraints
    6. Return everything for LLM scheduling
    """
    plan_context = orchestrator_plan.get("plan_context", {})
    flight_data = agent_outputs.get("flight_agent", {})

    logger.info("=" * 60)
    logger.info("🔧 [ITINERARY_BUILDER_nonVRP] Starting pipeline")

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

    logger.info("🔧 [ITINERARY_BUILDER_nonVRP] Pipeline completed")
    logger.info("=" * 60)

    return result
