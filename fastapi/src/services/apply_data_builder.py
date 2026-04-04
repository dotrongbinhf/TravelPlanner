"""
Apply Data Builder Service.

Normalizes agent outputs into a clean, flat format that the frontend
can directly POST to the .NET `POST /api/Plan/{id}/apply-ai` endpoint.

Handles:
- Itinerary: maps stop names → resolved placeIds, includes flight airport items,
  merges end_day→start_day into overnight hotel stays
- Budget: merges aggregated_costs into flat expense items with ExpenseCategory mapping
- Packing lists: passes through from preparation_agent
- Notes: passes through from preparation_agent
- Plan metadata: start/end dates, currency from plan_context
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── ExpenseCategory mapping ──────────────────────────────────────────────
# Maps cost_aggregator category keys → .NET ExpenseCategory enum values
# and preparation_agent budget "type" fields → .NET enum
AGGREGATED_CATEGORY_MAP = {
    "flights": "Transport",
    "accommodation": "Accomodation",
    "attractions": "Activities",
    "restaurants": "FoodAndDrink",
}

PREP_BUDGET_TYPE_MAP = {
    "Food & Drinks": "FoodAndDrink",
    "Transport": "Transport",
    "Activities": "Activities",
    "Shopping": "Shopping",
    "Other": "Other",
}

# Roles to SKIP entirely (origin-side airport events)
SKIP_ROLES = {"outbound_departure", "return_arrival"}


def _parse_time_minutes(time_str: str) -> int:
    """Parse "HH:MM" to total minutes since midnight."""
    if not time_str:
        return 0
    try:
        parts = time_str.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0


# ── Itinerary ────────────────────────────────────────────────────────────

def _build_itinerary_days(
    agent_outputs: dict[str, Any],
    plan_context: dict[str, Any],
) -> list[dict]:
    """Build itinerary days from itinerary_agent output.

    Includes:
    - Attractions, meals, generic activities with resolved placeIds
    - Outbound flight (outbound_arrival): full flight block
    - Return flight (return_departure): airport wait + flight block
    - Hotel overnight (end_day → start_day merge): single overnight item
    
    Skips:
    - outbound_departure, return_arrival (origin-side events)
    - start_day when previous day had end_day for same hotel
    """
    itinerary_data = agent_outputs.get("itinerary_agent", {})
    resolved_places = itinerary_data.get("resolved_places", {})
    restaurant_data = agent_outputs.get("restaurant_agent", {})
    flight_data = agent_outputs.get("flight_agent", {})

    # Build name → placeId lookup from resolved places
    name_to_place_id: dict[str, str] = {}
    for group_key in ("airports", "hotels", "attractions"):
        for item in resolved_places.get(group_key, []):
            resolved = item.get("resolved")
            if resolved:
                place_id = resolved.get("placeId", "")
                original_name = item.get("name", "")
                resolved_title = resolved.get("title", "")
                if place_id:
                    if original_name:
                        name_to_place_id[original_name.lower()] = place_id
                    if resolved_title:
                        name_to_place_id[resolved_title.lower()] = place_id

    # Build restaurant name → placeId lookup
    restaurant_place_ids: dict[str, str] = {}
    if restaurant_data and not restaurant_data.get("skipped"):
        for meal in restaurant_data.get("meals", []):
            r_name = meal.get("name", "")
            r_place_id = meal.get("place_id", "")
            if r_name and r_place_id:
                restaurant_place_ids[r_name.lower()] = r_place_id

    # Extract flight times for outbound/return items
    outbound_flight = flight_data.get("recommend_outbound_flight") if flight_data else None
    return_flight = flight_data.get("recommend_return_flight") if flight_data else None

    # Pre-process: build lookup of next day's start_day departure time,
    # and track which hotels had end_day (for start_day skipping)
    all_days = itinerary_data.get("days", [])
    end_day_hotels: dict[int, str] = {}  # day_idx → hotel name

    # Also collect start_day departure times per day for overnight duration calc
    start_day_departures: dict[int, str] = {}  # day_idx → departure time "HH:MM"
    for day_data in all_days:
        day_idx = day_data.get("day", 0)
        for stop in day_data.get("stops", []):
            if stop.get("role") == "start_day":
                start_day_departures[day_idx] = stop.get("departure", "")
            if stop.get("role") == "end_day":
                end_day_hotels[day_idx] = stop.get("name", "")

    days = []
    for day_data in all_days:
        day_idx = day_data.get("day", 0)
        items = []

        for stop in day_data.get("stops", []):
            role = stop.get("role", "")
            name = stop.get("name", "")
            arrival = stop.get("arrival", "")
            departure = stop.get("departure", "")

            # ── Skip origin-side airport events ──
            if role in SKIP_ROLES:
                continue

            # ── Skip start_day if previous night had end_day for same hotel ──
            if role == "start_day":
                prev_day_idx = day_idx - 1
                prev_end_hotel = end_day_hotels.get(prev_day_idx, "")
                if prev_end_hotel and prev_end_hotel.lower() == name.lower():
                    # Already covered by previous day's overnight stay
                    continue

            # ── Outbound arrival (destination airport) ──
            if role == "outbound_arrival":
                # Option A: full flight block
                # startTime = flight departure at origin, duration = flight time
                flight_dep = outbound_flight.get("departure_time", "") if outbound_flight else ""
                flight_arr = outbound_flight.get("arrival_time", "") if outbound_flight else arrival

                start_min = _parse_time_minutes(flight_dep) if flight_dep else _parse_time_minutes(arrival)
                end_min = _parse_time_minutes(flight_arr) if flight_arr else _parse_time_minutes(arrival)
                duration_minutes = max(0, end_min - start_min) if end_min > start_min else 0

                place_id = name_to_place_id.get(name.lower(), "")
                items.append({
                    "placeId": place_id,
                    "placeName": name,
                    "role": role,
                    "startTime": flight_dep or arrival,
                    "duration": duration_minutes if duration_minutes > 0 else 60,
                })
                continue

            # ── Return departure (destination airport) ──
            if role == "return_departure":
                # startTime = arrival at airport, duration = until flight departure
                flight_dep = return_flight.get("departure_time", "") if return_flight else departure

                start_min = _parse_time_minutes(arrival)
                end_min = _parse_time_minutes(flight_dep) if flight_dep else _parse_time_minutes(departure)
                duration_minutes = max(0, end_min - start_min) if end_min > start_min else 0

                place_id = name_to_place_id.get(name.lower(), "")
                items.append({
                    "placeId": place_id,
                    "placeName": name,
                    "role": role,
                    "startTime": arrival,
                    "duration": duration_minutes if duration_minutes > 0 else 60,
                })
                continue

            # ── End day (hotel overnight) ──
            if role == "end_day":
                # Duration spans from arrival tonight to next morning's start_day departure
                next_day_idx = day_idx + 1
                next_departure = start_day_departures.get(next_day_idx, "")

                start_min = _parse_time_minutes(arrival)
                if next_departure:
                    end_min = _parse_time_minutes(next_departure)
                    # Overnight: next morning time is smaller, so add 24h
                    if end_min <= start_min:
                        duration_minutes = (24 * 60 - start_min) + end_min
                    else:
                        duration_minutes = end_min - start_min
                else:
                    # Last night or no next day info — default 10h
                    duration_minutes = 10 * 60

                place_id = name_to_place_id.get(name.lower(), "")
                items.append({
                    "placeId": place_id,
                    "placeName": name,
                    "role": role,
                    "startTime": arrival,
                    "duration": duration_minutes,
                })
                continue

            # ── Regular stops (attractions, meals, generic, etc.) ──

            # Calculate duration
            duration_minutes = 0
            if arrival and departure:
                start_min = _parse_time_minutes(arrival)
                end_min = _parse_time_minutes(departure)
                duration_minutes = max(0, end_min - start_min)

            # Resolve placeId
            place_id = ""
            if role in ("lunch", "dinner"):
                place_id = restaurant_place_ids.get(name.lower(), "")
            elif role in ("attraction",):
                place_id = name_to_place_id.get(name.lower(), "")
            else:
                # Hotel roles (luggage_drop, luggage_pickup, midday_rest, start_day)
                # or generic activities
                place_id = name_to_place_id.get(name.lower(), "")

            items.append({
                "placeId": place_id,
                "placeName": name,
                "role": role,
                "startTime": arrival,
                "duration": duration_minutes if duration_minutes > 0 else 60,
            })

        days.append({
            "order": day_idx,
            "title": f"Day {day_idx + 1}",
            "items": items,
        })

    return days


# ── Budget / Expense Items ───────────────────────────────────────────────

def _build_expense_items(
    agent_outputs: dict[str, Any],
    plan_context: dict[str, Any],
    aggregated_costs: dict[str, Any] | None = None,
) -> list[dict]:
    """Flatten aggregated costs into a list of expense items.

    Maps category names from cost_aggregator to .NET ExpenseCategory enum values.
    For the "other" category (from preparation agent), maps using the budget "type" field.
    """
    if not aggregated_costs:
        return []

    items = []

    for cat_key, cat_data in aggregated_costs.get("categories", {}).items():
        dotnet_category = AGGREGATED_CATEGORY_MAP.get(cat_key, "Other")

        for cost_item in cat_data.get("items", []):
            name = cost_item.get("name", "")
            amount = cost_item.get("amount", 0)
            note = cost_item.get("note", "")

            # For "other" category, try to extract more specific mapping
            # from the [Type] prefix in name (e.g. "[Transport] Grab/taxi")
            actual_category = dotnet_category
            if cat_key == "other" and name.startswith("["):
                bracket_end = name.find("]")
                if bracket_end > 0:
                    type_str = name[1:bracket_end].strip()
                    actual_category = PREP_BUDGET_TYPE_MAP.get(type_str, "Other")
                    name = name[bracket_end + 1:].strip()  # Remove [Type] prefix

            display_name = f"{name} ({note})" if note else name

            items.append({
                "category": actual_category,
                "name": display_name,
                "amount": amount,
            })

    return items


# ── Packing Lists ────────────────────────────────────────────────────────

def _build_packing_lists(agent_outputs: dict[str, Any]) -> list[dict]:
    """Extract packing lists from preparation_agent output."""
    prep_data = agent_outputs.get("preparation_agent", {})
    if not prep_data or prep_data.get("skipped"):
        return []

    result = []
    for pl in prep_data.get("packing_lists", []):
        name = pl.get("name", "")
        items = pl.get("items", [])
        if name and items:
            result.append({
                "name": name,
                "items": items,  # list of strings
            })

    return result


# ── Notes ────────────────────────────────────────────────────────────────

def _build_notes(agent_outputs: dict[str, Any]) -> list[dict]:
    """Extract notes from preparation_agent output."""
    prep_data = agent_outputs.get("preparation_agent", {})
    if not prep_data or prep_data.get("skipped"):
        return []

    result = []
    for note in prep_data.get("notes", []):
        title = note.get("title", "")
        content = note.get("content", "")
        if title and content:
            result.append({
                "title": title,
                "content": content,
            })

    return result


# ── Main Builder ─────────────────────────────────────────────────────────

def build_apply_data(
    agent_outputs: dict[str, Any],
    plan_context: dict[str, Any],
    aggregated_costs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build normalized apply_data for frontend → .NET Apply endpoint.

    Returns a dict that the frontend can directly use as the body
    for POST /api/Plan/{id}/apply-ai (with mode added by frontend).
    """
    logger.info("🔨 [APPLY_DATA_BUILDER] Building apply_data...")

    itinerary_days = _build_itinerary_days(agent_outputs, plan_context)
    expense_items = _build_expense_items(agent_outputs, plan_context, aggregated_costs)
    packing_lists = _build_packing_lists(agent_outputs)
    notes = _build_notes(agent_outputs)

    apply_data = {
        "startTime": plan_context.get("start_date"),
        "endTime": plan_context.get("end_date"),
        "currencyCode": plan_context.get("currency", "VND"),
        "itineraryDays": itinerary_days,
        "expenseItems": expense_items,
        "packingLists": packing_lists,
        "notes": notes,
    }

    logger.info(
        f"🔨 [APPLY_DATA_BUILDER] Built: "
        f"{len(itinerary_days)} days, "
        f"{len(expense_items)} expense items, "
        f"{len(packing_lists)} packing lists, "
        f"{len(notes)} notes"
    )

    return apply_data
