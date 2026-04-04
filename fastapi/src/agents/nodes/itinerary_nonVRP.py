"""
Itinerary Agent Node (Non-VRP version).

Uses LLM to schedule attractions instead of OR-Tools VRP solver.
Receives distance matrix + opening hours + soft constraints from itinerary_builder_nonVRP,
then prompts the LLM to arrange the multi-day schedule.

Includes a validation loop that checks time-window violations and re-prompts
the LLM up to 2 times if violations are found.
"""

import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.state import GraphState
from src.services.itinerary_builder_nonVRP import run_itinerary_pipeline_nonVRP
from src.agents.nodes.utils import _extract_json
from src.config import settings

logger = logging.getLogger(__name__)

llm_itinerary = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)

MOCK = """```json
{
    "days": [
        {
            "day": 0,
            "stops": [
                {
                    "name": "Noi Bai International Airport",
                    "role": "outbound_arrival",
                    "arrival": "09:10",
                    "departure": "09:45"
                },
                {
                    "name": "The Oriental Jade Hotel",
                    "role": "luggage_drop",
                    "arrival": "10:45",
                    "departure": "11:15"
                },
                {
                    "name": "Lunch",
                    "role": "lunch",
                    "arrival": "11:30",
                    "departure": "13:00"
                },
                {
                    "name": "Explore Old Quarter",
                    "role": "generic",
                    "arrival": "13:15",
                    "departure": "14:00"
                },
                {
                    "name": "The Oriental Jade Hotel",
                    "role": "midday_rest",
                    "arrival": "14:00",
                    "departure": "15:30"
                },
                {
                    "name": "St. Joseph Cathedral",
                    "role": "attraction",
                    "souvenir": false,
                    "includes": [],
                    "arrival": "16:00",
                    "departure": "16:30"
                },
                {
                    "name": "Hanoi Opera House",
                    "role": "attraction",
                    "souvenir": false,
                    "includes": [],
                    "arrival": "17:00",
                    "departure": "17:45"
                },
                {
                    "name": "Dinner",
                    "role": "dinner",
                    "arrival": "18:00",
                    "departure": "19:30"
                },
                {
                    "name": "Hoàn Kiếm Lake",
                    "role": "attraction",
                    "souvenir": true,
                    "includes": ["Ngoc Son Temple", "The Huc Bridge"],
                    "arrival": "20:00",
                    "departure": "21:30"
                },
                {
                    "name": "The Oriental Jade Hotel",
                    "role": "end_day",
                    "arrival": "22:00",
                    "departure": ""
                }
            ]
        },
        {
            "day": 1,
            "stops": [
                {
                    "name": "The Oriental Jade Hotel",
                    "role": "start_day",
                    "arrival": "07:30",
                    "departure": "07:30"
                },
                {
                    "name": "Ho Chi Minh's Mausoleum",
                    "role": "attraction",
                    "souvenir": false,
                    "includes": ["One Pillar Pagoda", "Presidential Palace Historical Site"],
                    "arrival": "08:00",
                    "departure": "10:00"
                },
                {
                    "name": "Imperial Citadel of Thang Long",
                    "role": "attraction",
                    "souvenir": false,
                    "includes": [],
                    "arrival": "10:30",
                    "departure": "12:30"
                },
                {
                    "name": "Lunch",
                    "role": "lunch",
                    "arrival": "12:45",
                    "departure": "14:15"
                },
                {
                    "name": "Temple Of Literature",
                    "role": "attraction",
                    "souvenir": true,
                    "includes": [],
                    "arrival": "14:45",
                    "departure": "16:15"
                },
                {
                    "name": "Hoa Lo Prison",
                    "role": "attraction",
                    "souvenir": false,
                    "includes": [],
                    "arrival": "16:45",
                    "departure": "18:15"
                },
                {
                    "name": "Dinner",
                    "role": "dinner",
                    "arrival": "18:30",
                    "departure": "20:00"
                },
                {
                    "name": "The Oriental Jade Hotel",
                    "role": "end_day",
                    "arrival": "20:30",
                    "departure": ""
                }
            ]
        },
        {
            "day": 2,
            "stops": [
                {
                    "name": "The Oriental Jade Hotel",
                    "role": "start_day",
                    "arrival": "09:00",
                    "departure": "09:00"
                },
                {
                    "name": "Vietnam Museum of Ethnology",
                    "role": "attraction",
                    "souvenir": false,
                    "includes": [],
                    "arrival": "09:30",
                    "departure": "12:00"
                },
                {
                    "name": "Lunch",
                    "role": "lunch",
                    "arrival": "12:15",
                    "departure": "13:45"
                },
                {
                    "name": "Hanoi Old Quarter",
                    "role": "attraction",
                    "souvenir": true,
                    "includes": [],
                    "arrival": "14:15",
                    "departure": "16:15"
                },
                {
                    "name": "Explore Old Quarter (shopping/cafes)",
                    "role": "generic",
                    "arrival": "16:15",
                    "departure": "17:45"
                },
                {
                    "name": "Dinner",
                    "role": "dinner",
                    "arrival": "18:00",
                    "departure": "19:30"
                },
                {
                    "name": "The Oriental Jade Hotel",
                    "role": "end_day",
                    "arrival": "20:00",
                    "departure": ""
                }
            ]
        },
        {
            "day": 3,
            "stops": [
                {
                    "name": "The Oriental Jade Hotel",
                    "role": "start_day",
                    "arrival": "09:00",
                    "departure": "09:00"
                },
                {
                    "name": "Hanoi Old Quarter (last-minute shopping)",
                    "role": "attraction",
                    "souvenir": true,
                    "includes": [],
                    "arrival": "09:30",
                    "departure": "11:30"
                },
                {
                    "name": "The Oriental Jade Hotel",
                    "role": "luggage_pickup",
                    "arrival": "12:00",
                    "departure": "12:30"
                },
                {
                    "name": "Lunch",
                    "role": "lunch",
                    "arrival": "12:45",
                    "departure": "14:15"
                },
                {
                    "name": "Noi Bai International Airport",
                    "role": "return_departure",
                    "arrival": "15:15",
                    "departure": "17:30"
                }
            ]
        }
    ],
    "dropped": [],
    "more_attractions": [
        {
            "name": "Ho Chi Minh Museum",
            "source": "includes",
            "parent": "Ho Chi Minh's Mausoleum",
            "reason": "Skipped from the Ho Chi Minh Mausoleum complex due to time constraints."
        },
        {
            "name": "Dong Xuan Market",
            "source": "itinerary_agent",
            "reason": "A bustling local market in the Old Quarter, great for local life and souvenirs."
        },
        {
            "name": "Tran Quoc Pagoda",
            "source": "itinerary_agent",
            "reason": "Hanoi's oldest pagoda on West Lake, beautiful architecture and serene views."
        }
    ],
    "notes": "Moderate pace itinerary covering all input attractions with meals and rest. Day 0 includes midday rest after luggage drop. Ho Chi Minh's Mausoleum scheduled Saturday morning for opening hours. Old Quarter visited multiple times for exploration and souvenirs."
}
```"""

ITINERARY_SCHEDULER_SYSTEM = """You are the Itinerary Scheduling Agent. You receive a list of attractions with opening hours, a distance matrix between all locations, and schedule constraints. Your job is to arrange them into a natural, optimized multi-day travel schedule.

## Input You Receive
1. **Attractions list**: Each with name, opening hours per day, suggested duration (adjustable), and must_visit flag
2. **Distance matrix**: Travel times (in minutes) between all locations — these are RAW actual travel times
3. **Schedule constraints**: Day 0 arrival info, last day deadline, hotels per night, luggage logistics, pace

## How to Schedule

### Priority: REALISTIC over PACKED
- DO NOT try to fit every single attraction into the schedule. Prioritize a natural, enjoyable experience over cramming everything in.
- Leave reasonable gaps between stops — travelers need time to walk, take photos, buy drinks, use restrooms, etc.
- The `pace` field in constraints determines the daily rhythm:
  - **relaxed**: Start later, end earlier. Longer visits at each place, more breaks and free time. Prefer depth over breadth — it's okay to see fewer places and enjoy them more.
  - **moderate**: Balanced day. Reasonable start and end times. Mix of longer and shorter visits.
  - **packed**: Start early, end late. Shorter visits, tighter gaps. Maximize the number of places visited — but still MUST include proper meals and respect opening hours.
- It's BETTER to drop some places and have a relaxing trip than to rush through everything.

### Distance, Time & Buffer
- The distance matrix gives RAW travel times. When scheduling, you MUST add a reasonable buffer on top to account for:
  - Traffic, parking, walking to/from transport
  - Flexibility if the previous stop runs late or early
  - Making the schedule easy to read and remember (clean round times)
- **Buffer guidelines**:
  - Short routes (≤10 min raw): round up to ~15 min total
  - Medium routes (11-30 min raw): add ~10-15 min buffer
  - Long routes (>30 min raw): add ~15-20 min buffer
  - Example: raw 12 min → depart 11:00, arrive ~11:30. Raw 40 min → depart 14:00, arrive ~15:00.
- Round arrival times to multiples of 15 minutes (09:00, 09:15, 09:30, 09:45) for a clean, easy-to-follow schedule
- Group geographically close attractions on the same day (use travel times to determine proximity)

### Opening Hours & Hotel
- Respect opening hours: arrival ≥ opening time, departure ≤ closing time
- If you would arrive at an attraction BEFORE it opens, try to rearrange the order, visit somewhere else first, or start the day later. Small waits (≤15 min) are acceptable but avoid scheduling long idle waits.
- You decide daily start and end times based on the pace, logistics, and what feels natural
- On the first day, consider arrival time — travelers may need to drop luggage, rest, etc.
- On the last day, respect the hard deadline for departure (flight or transport)
- Hotel check-in/check-out times are provided per hotel in the constraints. On check-out day, you MUST leave the hotel BEFORE check-out time. On check-in day, luggage can be dropped off before check-in time, but the room is only available from check-in time.
- If midday rest is SUGGESTED for a day, evaluate whether it makes sense: skip if the day starts late, schedule is already short, or there's not enough time. Keep it if travelers started early, have young children, or the day would be exhaustingly long. If scheduled on a check-in day, it MUST be AFTER the hotel's check-in time.

### Meals — MANDATORY
- Lunch MUST be scheduled between 11:00-12:30 (~90 min). Dinner MUST be between 18:00-20:00 (~90 min).
- Meals are NOT optional. Every day MUST have lunch AND dinner unless:
  - **Skip lunch ONLY IF** the day starts AFTER 13:00 (e.g., flight arrives at 15:00)
  - **Skip dinner ONLY IF** the day ends BEFORE 18:00 (e.g., flight departs at 16:00)
- DO NOT replace a meal with an attraction. If it's meal time, schedule the meal.
- DO NOT schedule an attraction visit that overlaps with meal windows. If it's about lunch time (example: 11:00), go eat — don't start an attraction visit.
- When approaching a meal window, finish the current attraction first, then eat, then continue.
- **Meal distance rule**: Restaurants are found near each meal location AFTER scheduling, so assume meals happen near the previous attraction:
  - Previous stop (A) → meal: travel is ~15 min (walk to nearby restaurant)
  - Meal → next stop (B): travel = same as A → B from the distance matrix (restaurant is near A)

### Includes (Sub-attractions)
- Some attractions have an "includes" field listing sub-attractions that are WITHIN or ADJACENT to them (e.g., Hoan Kiem Lake includes Ngoc Son Temple)
- The suggested_duration_minutes already covers all included sub-attractions
- In your output, add an "includes" field to each attraction stop listing which included sub-places you recommend visiting at that stop
- Not all includes need to be visited — choose based on available time, traveler interest, and pace
- If an attraction has no includes, set "includes" to an empty list []

### Adding & Dropping
- You MAY adjust visit durations — the suggested duration is a guide, not mandatory
- **Dropping stops**: You MAY drop non-must-visit attractions if the schedule is too packed. must_visit attractions MUST appear in the schedule. It's BETTER to drop some places and have a relaxing trip than to rush through everything.
- **Adding activities**: If a day has gaps of 2+ hours with nothing to do, you MUST either rearrange the schedule to eliminate the gap OR suggest additional activities to fill it. Activities can include: walking around the area, visiting a nearby park, exploring local markets, or free-time activities. Add these as stops with role "generic" (NOT "attraction") and a reasonable duration. Use descriptive names like "Explore Old Quarter", "Walk around Hoan Kiem Lake area". The "generic" role is ONLY for activities YOU suggest that are NOT in the input attractions list.
- If souvenir_shopping is mentioned, set `"souvenir": true` on attraction stops where buying souvenirs would be convenient (e.g., near markets, cultural sites, tourist areas). Multiple stops can have souvenir=true.

## Available Roles
Boundary stops (arrival = departure is allowed):
- `start_day`: Daily start point (hotel). Just departing — arrival = departure.
- `end_day`: Daily end point (hotel). Just arriving — departure can be empty "".
- `outbound_arrival`: Arrival at destination (airport/station). arrival = landing time, departure = after clearance.
- `return_departure`: Departure from destination (airport/station). arrival ~ 2h BEFORE flight departure time, departure = actual flight departure time.

Intermediate stops (departure must be AFTER arrival):
- `attraction`: Tourist attraction FROM THE INPUT LIST. Visit ≥ 30 min. Has extra fields `"souvenir": true/false` and `"includes": [list]`.
- `generic`: Activity suggested by YOU (not in input). Visit ≥ 30 min. Use this role ONLY for your own suggestions.
- `lunch`: Lunch break. ~60-90 min.
- `dinner`: Dinner break. ~90 min.
- `midday_rest`: Hotel rest. ~90-120 min.
- `luggage_drop`: Drop luggage at hotel. ~15-30 min.
- `luggage_pickup`: Pick up luggage from hotel. ~15-30 min.

## Response Format
CRITICAL: Output ONLY a raw JSON object. No text before or after. No markdown fences.

Each stop needs ONLY: `name`, `role`, `arrival` (HH:MM), `departure` (HH:MM).
Attraction stops also need: `souvenir` (bool), `includes` (list).
Do NOT include duration, minutes, or travel time fields — the validator computes these automatically.

{
    "days": [
        {
            "day": 0,
            "stops": [
                {
                    "name": "Noi Bai International Airport",
                    "role": "outbound_arrival",
                    "arrival": "09:00",
                    "departure": "09:30"
                },
                {
                    "name": "Hotel X",
                    "role": "luggage_drop",
                    "arrival": "10:15",
                    "departure": "10:45"
                },
                {
                    "name": "Temple of Literature",
                    "role": "attraction",
                    "souvenir": true,
                    "includes": [],
                    "arrival": "11:00",
                    "departure": "12:30"
                },
                {
                    "name": "Lunch",
                    "role": "lunch",
                    "arrival": "12:45",
                    "departure": "14:15"
                },
                {
                    "name": "Ho Chi Minh Mausoleum",
                    "role": "attraction",
                    "souvenir": false,
                    "includes": ["One Pillar Pagoda"],
                    "arrival": "14:45",
                    "departure": "16:15"
                },
                {
                    "name": "Dinner",
                    "role": "dinner",
                    "arrival": "18:00",
                    "departure": "19:30"
                },
                {
                    "name": "Hotel X",
                    "role": "end_day",
                    "arrival": "19:45",
                    "departure": ""
                }
            ]
        }
    ],
    "dropped": ["Attraction name that could not fit"],
    "more_attractions": [
        {"name": "Vietnam Museum of Ethnology", "source": "attraction_agent", "reason": "Not enough time on this trip"},
        {"name": "Ho Chi Minh Museum", "source": "includes", "parent": "Ho Chi Minh Mausoleum", "reason": "Skipped from includes due to time"},
        {"name": "Explore Dong Xuan Market", "source": "itinerary_agent", "reason": "Great for local shopping and street food"}
    ],
    "notes": "Brief explanation of scheduling decisions"
}

## Critical Rules
- All times are HH:MM format (24-hour clock)
- For intermediate stops: departure MUST be AFTER arrival (you spend time there)
- For `start_day`: arrival = departure (you just leave)
- For `end_day`: departure = "" (you just arrive for the night)
- The gap between one stop's departure and the next stop's arrival must be enough for the raw travel time (with buffer added)
- If two consecutive stops are at the SAME location (e.g., hotel → luggage_drop at same hotel), the next arrival can equal the current departure (no travel needed)
- For meals (lunch/dinner): previous stop → meal = ~15 min (walk to nearby restaurant). Meal → next stop = same travel time as previous stop → next stop (restaurant is near previous stop)
- Each day starts with `start_day` (or `outbound_arrival` on day 0) and ends with `end_day` (or `return_departure` on last day)
- NEVER schedule an attraction during "Closed" hours
- NEVER exceed an attraction's closing time with your departure
- must_visit = true → attraction MUST be in the schedule
- Every attraction stop MUST have an "includes" field (list of sub-attraction names visited at that stop, or empty list [])
- The "more_attractions" list MUST include: (1) attractions from the input that were dropped, (2) sub-attractions from "includes" that were skipped, and (3) your own suggestions of interesting places near the destination that weren't in the input. For each entry, specify "source" ("attraction_agent", "includes", or "itinerary_agent"), optionally "parent" (if source is "includes"), and "reason" (brief explanation why it's worth considering)
"""


# ============================================================================
# VALIDATION
# ============================================================================

def _time_to_minutes(time_str: str) -> int:
    """Parse 'HH:MM' to minutes since midnight."""
    if not time_str:
        return 0
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _parse_opening_range(hours_str: str) -> tuple[int, int] | None:
    """Parse '08:00-17:00' to (open_min, close_min). None if 'Closed'."""
    s = hours_str.strip().lower()
    if s == "closed":
        return None
    if "open 24" in s or "24 hours" in s:
        return (0, 1440)

    raw = hours_str.strip().replace("(assumed)", "").strip()
    raw = raw.replace('\u2013', '-').replace('\u2014', '-')

    ranges = [r.strip() for r in raw.split(",")]
    earliest, latest = 1440, 0

    for r in ranges:
        parts = r.split("-")
        if len(parts) != 2:
            continue
        try:
            o = _time_to_minutes(parts[0].strip())
            c = _time_to_minutes(parts[1].strip())
            if c > o:
                earliest = min(earliest, o)
                latest = max(latest, c)
        except (ValueError, IndexError):
            continue

    return (earliest, latest) if earliest < latest else None


def _validate_schedule(
    schedule: dict,
    attractions_info: list[dict],
    schedule_constraints: dict | None = None,
    distance_pairs: list[dict] | None = None,
) -> list[dict]:
    """
    Validate LLM schedule against all constraints.
    All arithmetic is done by code — LLM only provides arrival/departure HH:MM.

    Checks:
    1. Travel feasibility: gap between stops >= raw travel time
    2. Opening hours (attractions only)
    3. Hotel check-out time on check-out day
    4. Last day deadline
    5. Must-visit attractions present
    6. Midday rest after hotel check-in time on check-in day
    7. Intermediate stops: departure > arrival (positive duration)
    8. Mandatory meals (lunch/dinner)
    9. Mandatory daily start/end structure
    10. Reasonable duration (attraction >= 30min, meal >= 45min)

    Returns list of violation dicts.
    """
    violations = []
    constraints = schedule_constraints or {}
    attr_hours = {info["name"]: info["opening_hours"] for info in attractions_info}

    # --- Build raw distance lookup (symmetric) ---
    raw_lookup = {}  # (name_a, name_b) -> raw_minutes
    for pair in (distance_pairs or []):
        a, b = pair["from"], pair["to"]
        raw = pair["raw_minutes"]
        raw_lookup[(a, b)] = raw
        raw_lookup[(b, a)] = raw

    # --- Check 5: Must-visit presence ---
    must_visit_names = {info["name"] for info in attractions_info if info.get("must_visit")}
    scheduled_attractions = set()
    for day_data in schedule.get("days", []):
        for stop in day_data.get("stops", []):
            if stop.get("role") == "attraction":
                scheduled_attractions.add(stop.get("name", ""))

    for missing in must_visit_names - scheduled_attractions:
        violations.append({
            "day": -1, "stop_name": missing,
            "issue": f"MUST-VISIT attraction '{missing}' is NOT in the schedule",
        })

    # --- Build hotel check-out/check-in lookup ---
    hotel_checkout_map = {}  # day_idx -> (hotel_name, co_time_min)
    hotel_checkin_map = {}   # day_idx -> (hotel_name, ci_time_min)
    for h in constraints.get("hotels", []):
        co_day = h.get("check_out_day")
        co_time = h.get("check_out_time", "12:00")
        if co_day is not None:
            hotel_checkout_map[co_day] = (h["name"], _time_to_minutes(co_time))
        ci_day = h.get("check_in_day")
        ci_time = h.get("check_in_time", "14:00")
        if ci_day is not None:
            hotel_checkin_map[ci_day] = (h["name"], _time_to_minutes(ci_time))

    # --- Last day deadline ---
    deadline = constraints.get("last_day_deadline", {})
    deadline_time_min = _time_to_minutes(deadline.get("deadline_time", "")) if deadline.get("deadline_time") else None
    num_days = constraints.get("num_days", 0)
    last_day_idx = num_days - 1 if num_days > 0 else None

    # --- Per-day checks ---
    for day_data in schedule.get("days", []):
        day_idx = day_data.get("day", 0)
        stops = day_data.get("stops", [])

        effective_location = ""  # last non-meal stop name for meal distance rule

        for stop_idx, stop in enumerate(stops):
            name = stop.get("name", "")
            role = stop.get("role", "")
            arrival_str = stop.get("arrival", "")
            departure_str = stop.get("departure", "")

            # Parse times (code does all arithmetic)
            arrival_min = _time_to_minutes(arrival_str)
            departure_min = _time_to_minutes(departure_str) if departure_str else arrival_min
            duration = departure_min - arrival_min

            # --- Check 7: Intermediate stops must have positive duration ---
            intermediate_roles = {"attraction", "generic", "lunch", "dinner", "midday_rest", "luggage_drop", "luggage_pickup"}
            if role in intermediate_roles:
                if duration <= 0:
                    violations.append({
                        "day": day_idx, "stop_name": name,
                        "issue": f"Role '{role}' must have departure AFTER arrival, but arrival={arrival_str} departure={departure_str}",
                    })

            # --- Check 10: Reasonable duration ---
            if role in ("attraction", "generic") and 0 < duration < 30:
                violations.append({
                    "day": day_idx, "stop_name": name,
                    "issue": f"Visit duration is only {duration}min (arrival={arrival_str}, departure={departure_str}). Minimum recommended: 30min.",
                })
            if role in ("lunch", "dinner") and 0 < duration < 45:
                violations.append({
                    "day": day_idx, "stop_name": name,
                    "issue": f"Meal duration is only {duration}min (arrival={arrival_str}, departure={departure_str}). Minimum recommended: 45min.",
                })

            # --- Check 1: Travel feasibility (gap >= raw travel time) ---
            if stop_idx > 0:
                prev_stop = stops[stop_idx - 1]
                prev_role = prev_stop.get("role", "")
                prev_name = prev_stop.get("name", "")
                prev_dep_str = prev_stop.get("departure", "")
                prev_dep_min = _time_to_minutes(prev_dep_str) if prev_dep_str else _time_to_minutes(prev_stop.get("arrival", ""))

                gap = arrival_min - prev_dep_min

                # Determine required travel time using meal distance rule
                if role in ("lunch", "dinner"):
                    # A -> meal: ~15 min walk to nearby restaurant
                    required = 15
                elif prev_role in ("lunch", "dinner"):
                    # meal -> B: same as effective_location -> B (restaurant is near prev attraction)
                    if effective_location == name:
                        required = 0
                    else:
                        required = raw_lookup.get((effective_location, name), 0)
                elif prev_name == name:
                    # Same location (e.g., hotel -> luggage_drop at same hotel)
                    required = 0
                else:
                    required = raw_lookup.get((prev_name, name), 0)

                if gap < required:
                    gap_display = f"{gap}min" if gap >= 0 else f"{gap}min (OVERLAP!)"
                    violations.append({
                        "day": day_idx, "stop_name": name,
                        "issue": f"Gap from '{prev_name}' (dep {prev_dep_str}) to '{name}' (arr {arrival_str}) is {gap_display}, but raw travel time is {required}min. Need to depart earlier or arrive later.",
                    })

            # --- Check 2: Opening hours (attractions only) ---
            if role == "attraction":
                hours = attr_hours.get(name)
                if hours:
                    day_key = None
                    for k in hours:
                        if k.startswith(f"day_{day_idx}"):
                            day_key = k
                            break

                    if day_key:
                        hours_str = hours[day_key]
                        if hours_str.strip().lower() == "closed":
                            violations.append({
                                "day": day_idx, "stop_name": name,
                                "issue": f"CLOSED on day {day_idx}",
                            })
                        else:
                            window = _parse_opening_range(hours_str)
                            if window:
                                open_min, close_min = window
                                if arrival_min < open_min:
                                    violations.append({
                                        "day": day_idx, "stop_name": name,
                                        "issue": f"Arrives at {arrival_str} but opens at {open_min//60:02d}:{open_min%60:02d}",
                                    })
                                if departure_min > close_min:
                                    violations.append({
                                        "day": day_idx, "stop_name": name,
                                        "issue": f"Departs at {departure_str} but closes at {close_min//60:02d}:{close_min%60:02d}",
                                    })

            # --- Check 3: Hotel check-out on check-out day ---
            if role == "start_day" and day_idx in hotel_checkout_map:
                co_hotel_name, co_time_min = hotel_checkout_map[day_idx]
                if departure_min > co_time_min:
                    violations.append({
                        "day": day_idx, "stop_name": name,
                        "issue": f"Departs hotel at {departure_str} but check-out time is {co_time_min//60:02d}:{co_time_min%60:02d}",
                    })

            # --- Check 6: Midday rest on check-in day must be after check-in time ---
            if role == "midday_rest" and day_idx in hotel_checkin_map:
                ci_hotel_name, ci_time_min = hotel_checkin_map[day_idx]
                if arrival_min < ci_time_min:
                    violations.append({
                        "day": day_idx, "stop_name": name,
                        "issue": f"Midday rest at {arrival_str} but hotel check-in is at {ci_time_min//60:02d}:{ci_time_min%60:02d}. Room not available yet.",
                    })

            # Track effective location (for meal distance rule)
            if role not in ("lunch", "dinner"):
                effective_location = name

        # --- Check 4: Last day deadline ---
        if last_day_idx is not None and day_idx == last_day_idx and deadline_time_min:
            last_stop = stops[-1] if stops else None
            if last_stop:
                last_arrival_min = _time_to_minutes(last_stop.get("arrival", ""))
                if last_arrival_min > deadline_time_min:
                    violations.append({
                        "day": day_idx, "stop_name": last_stop.get("name", ""),
                        "issue": f"Arrives at final stop at {last_stop.get('arrival', '')} but deadline is {deadline_time_min//60:02d}:{deadline_time_min%60:02d}",
                    })

        # --- Check 8: Mandatory meals (lunch/dinner) ---
        if stops:
            first_dep_min = _time_to_minutes(stops[0].get("departure", stops[0].get("arrival", "")))
            last_arr_min = _time_to_minutes(stops[-1].get("arrival", ""))
            roles_in_day = {s.get("role") for s in stops}

            # Lunch required if schedule spans past 13:00
            if first_dep_min < 780 and last_arr_min > 780:
                if "lunch" not in roles_in_day:
                    violations.append({
                        "day": day_idx, "stop_name": "Lunch",
                        "issue": f"Day {day_idx} has activity before 13:00 and after 13:00 but NO lunch scheduled",
                    })

            # Dinner required if schedule spans past 18:00
            if first_dep_min < 1080 and last_arr_min > 1080:
                if "dinner" not in roles_in_day:
                    violations.append({
                        "day": day_idx, "stop_name": "Dinner",
                        "issue": f"Day {day_idx} has activity after 18:00 but NO dinner scheduled",
                    })

        # --- Check 9: Mandatory daily start/end structure ---
        if stops:
            first_role = stops[0].get("role", "")
            last_role = stops[-1].get("role", "")
            is_first_day = (day_idx == 0)
            is_last_day = (last_day_idx is not None and day_idx == last_day_idx)

            if is_first_day:
                if first_role not in ("outbound_arrival", "start_day"):
                    violations.append({
                        "day": day_idx, "stop_name": stops[0].get("name", ""),
                        "issue": f"Day 0 must START with 'outbound_arrival' or 'start_day', got '{first_role}'",
                    })
            else:
                if first_role != "start_day":
                    violations.append({
                        "day": day_idx, "stop_name": stops[0].get("name", ""),
                        "issue": f"Day {day_idx} must START with 'start_day' (hotel), got '{first_role}'",
                    })

            if is_last_day:
                if last_role not in ("return_departure", "end_day"):
                    violations.append({
                        "day": day_idx, "stop_name": stops[-1].get("name", ""),
                        "issue": f"Last day must END with 'return_departure' or 'end_day', got '{last_role}'",
                    })
            else:
                if last_role != "end_day":
                    violations.append({
                        "day": day_idx, "stop_name": stops[-1].get("name", ""),
                        "issue": f"Day {day_idx} must END with 'end_day' (return to hotel), got '{last_role}'",
                    })

    return violations


# ============================================================================
# AGENT NODE
# ============================================================================

async def itinerary_nonVRP_agent_node(state: GraphState) -> dict[str, Any]:
    """Itinerary Agent (Non-VRP) — Uses LLM to schedule attractions.

    Flow:
        1. Pipeline: extract → resolve → distance matrix → opening hours → constraints
        2. Prompt LLM with all data
        3. Validate schedule against opening hours
        4. Re-prompt if violations (max 2 retries)
        5. Return schedule
    """
    logger.info("=" * 60)
    logger.info("📅 [ITINERARY_AGENT_nonVRP] Node entered")

    agent_outputs = state.get("agent_outputs", {})
    plan = state.get("orchestrator_plan", {})
    plan_context = plan.get("plan_context", {})

    itinerary_result = {}
 
    useRouteMatrix = False

    try:
        # Phase 1: Build scheduling input
        logger.info("📅 [ITINERARY_AGENT_nonVRP] Phase 1: Building scheduling input...")
        pipeline_data = await run_itinerary_pipeline_nonVRP(agent_outputs, plan, useRouteMatrix)

        if pipeline_data.get("error"):
            itinerary_result = {
                "error": True,
                "message": pipeline_data.get("message", "Pipeline failed"),
                "days": [], "dropped": [], "method": "llm",
            }
        else:
            # Phase 2: LLM scheduling
            logger.info("📅 [ITINERARY_AGENT_nonVRP] Phase 2: LLM scheduling...")
            human_content = _build_scheduling_prompt(pipeline_data, plan_context)

            messages = [
                SystemMessage(content=ITINERARY_SCHEDULER_SYSTEM),
                HumanMessage(content=human_content),
            ]

            max_retries = 2
            best_schedule = None
            violations = []

            for attempt in range(max_retries + 1):
                logger.info(f"   Attempt {attempt + 1}/{max_retries + 1}: Invoking LLM...")
                result = await llm_itinerary.ainvoke(messages)
                schedule = _extract_json(result.content)
                # schedule = _extract_json(MOCK)

                violations = _validate_schedule(schedule, pipeline_data["attractions_info"], pipeline_data["schedule_constraints"], pipeline_data["distance_pairs"])

                if not violations:
                    logger.info(f"   ✅ Valid on attempt {attempt + 1}")
                    best_schedule = schedule
                    break

                logger.warning(f"   ⚠️ {len(violations)} violations on attempt {attempt + 1}")
                for v in violations:
                    logger.warning(f"      Day {v['day']}: {v['stop_name']} — {v['issue']}")

                best_schedule = schedule

                if attempt < max_retries:
                    violation_text = "\n".join(
                        f"- Day {v['day']}: {v['stop_name']} — {v['issue']}" for v in violations
                    )
                    messages.append(AIMessage(content=result.content))
                    messages.append(HumanMessage(content=(
                        f"Your schedule has {len(violations)} violations:\n{violation_text}\n\n"
                        f"Fix these and return the COMPLETE corrected JSON schedule."
                    )))

            itinerary_result = best_schedule or {"days": [], "dropped": []}
            itinerary_result["method"] = "llm"
            itinerary_result["error"] = False

            if violations:
                itinerary_result["has_violations"] = True
                itinerary_result["violations"] = violations

            itinerary_result["plan_context"] = {
                "start_date": plan_context.get("start_date", ""),
                "end_date": plan_context.get("end_date", ""),
                "num_days": plan_context.get("num_days", 0),
                "destination": plan_context.get("destination", ""),
            }
            itinerary_result["resolved_places_count"] = pipeline_data.get("resolved_places_count", 0)
            itinerary_result["total_places_count"] = pipeline_data.get("total_places_count", 0)
            itinerary_result["resolved_places"] = pipeline_data.get("resolved_places", {})

    except Exception as e:
        logger.error(f"   ❌ Itinerary Agent (nonVRP) error: {e}", exc_info=True)
        itinerary_result = {"error": True, "message": str(e), "days": [], "dropped": [], "method": "llm"}

    num_days = len(itinerary_result.get("days", []))
    dropped = len(itinerary_result.get("dropped", []))

    logger.info(f"📅 [ITINERARY_AGENT_nonVRP] Completed: {num_days} days, {dropped} dropped")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"itinerary_agent": itinerary_result},
        "messages": [AIMessage(content=f"[Itinerary Agent] Created {num_days}-day LLM-scheduled itinerary ({dropped} places dropped)")],
    }


# ============================================================================
# PROMPT BUILDER
# ============================================================================

def _build_scheduling_prompt(pipeline_data: dict, plan_context: dict) -> str:
    """Build the human message for the LLM scheduler."""

    attractions_info = pipeline_data["attractions_info"]
    distance_pairs = pipeline_data["distance_pairs"]
    constraints = pipeline_data["schedule_constraints"]
    mobility_plan = plan_context.get("mobility_plan", {})

    # --- Attractions ---
    sections = ["## Attractions to Schedule\n"]
    for attr in attractions_info:
        must = " ⭐ MUST VISIT" if attr.get("must_visit") else ""
        seg = f" [{attr['segment_name']}]" if attr.get("segment_name") else ""
        sections.append(f"### {attr['name']}{must}{seg}")
        sections.append(f"- Suggested duration: {attr['suggested_duration_minutes']} min")
        if attr.get("includes"):
            inc_names = [i.get("name", str(i)) if isinstance(i, dict) else str(i) for i in attr["includes"]]
            sections.append(f"- Includes (sub-attractions within/adjacent): {', '.join(inc_names)}")
        if attr.get("notes"):
            sections.append(f"- Notes: {attr['notes']}")
        sections.append("- Opening hours:")
        for day_key, hours in attr["opening_hours"].items():
            sections.append(f"  - {day_key}: {hours}")
        sections.append("")

    # --- Distance Matrix ---
    sections.append("## Travel Times (raw minutes, symmetric)")
    sections.append("| From | To | Travel Time (min) |")
    sections.append("|------|----|-------------------|")
    for pair in distance_pairs:
        sections.append(f"| {pair['from']} | {pair['to']} | {pair['raw_minutes']} |")
    sections.append("")

    # --- Constraints ---
    sections.append("## Schedule Constraints")
    sections.append(f"- Days: {constraints['num_days']}")
    sections.append(f"- Start date: {constraints.get('start_date', 'N/A')}")
    sections.append(f"- Pace: {constraints.get('pace', 'moderate')}")
    sections.append(f"- Transport: {constraints.get('local_transportation', 'car')}")
    sections.append(f"- Travel by: {constraints.get('travel_by', 'flight')}")

    # Day 0 arrival
    arrival = constraints.get("day_0_arrival")
    if arrival:
        sections.append(f"\n### Day 0 Arrival")
        sections.append(f"- Location: {arrival.get('location', '?')}")
        sections.append(f"- Arrival time: {arrival.get('arrival_time', '?')}")
        if arrival.get("ready_time"):
            sections.append(f"- Ready to explore: {arrival['ready_time']}")
        sections.append(f"- Note: {arrival.get('note', '')}")

    # Last day deadline
    deadline = constraints.get("last_day_deadline")
    if deadline:
        sections.append(f"\n### Last Day Deadline (HARD CONSTRAINT)")
        sections.append(f"- Must be at: {deadline.get('location', '?')}")
        sections.append(f"- By: {deadline.get('deadline_time', '?')}")
        sections.append(f"- Note: {deadline.get('note', '')}")

    # Hotels
    hotels = constraints.get("hotels", [])
    if hotels:
        sections.append(f"\n### Hotels")
        for h in hotels:
            ci_day = f"day {h['check_in_day']}" if 'check_in_day' in h else '?'
            co_day = f"day {h['check_out_day']}" if 'check_out_day' in h else '?'
            sections.append(
                f"- {h['name']} ({h.get('segment_name', '')}): "
                f"check-in {h.get('check_in_date', '?')} ({ci_day}) at {h.get('check_in_time', '14:00')}, "
                f"check-out {h.get('check_out_date', '?')} ({co_day}) by {h.get('check_out_time', '12:00')}"
            )

    # Luggage
    luggage = constraints.get("luggage")
    if luggage:
        sections.append(f"\n### Luggage")
        sections.append(f"- {luggage.get('drop_luggage', '')}")
        sections.append(f"- {luggage.get('pick_up_luggage', '')}")

    # Midday rest
    if constraints.get("midday_rest_days"):
        sections.append(f"\n### Midday Rest (SUGGESTED — you decide based on actual schedule)")
        sections.append(f"- Suggested days: {constraints['midday_rest_days']}")
        if constraints.get("midday_rest_note"):
            sections.append(f"- {constraints['midday_rest_note']}")

    # Mobility plan
    if constraints.get("mobility_plan_description"):
        sections.append(f"\n### Trip Logistics")
        sections.append(constraints["mobility_plan_description"])

    sections.append("\nCreate the optimized schedule now. Output ONLY the JSON.")

    return "\n".join(sections)
