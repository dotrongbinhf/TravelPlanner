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
from langchain_openai import ChatOpenAI

from src.agents.state import GraphState
from src.services.itinerary_builder_nonVRP import run_itinerary_pipeline_nonVRP
from src.agents.nodes.utils import _extract_json
from src.config import settings

logger = logging.getLogger(__name__)

useRouteMatrix = settings.USE_ROUTE_MATRIX

# USE_VERCEL_AI_GATEWAY = True

llm_itinerary = (
    ChatOpenAI(
        model="google/gemini-2.5-flash",
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    # if USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview",
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_ITINERARY,
        temperature=0.3,
        streaming=False,
    )
)

ITINERARY_SCHEDULER_SYSTEM = """You are the Itinerary Scheduling Agent. You receive a list of attractions with opening hours, a distance matrix between all locations, and schedule constraints. Your job is to arrange them into a natural, optimized multi-day travel schedule.

## Input You Receive
1. **Attractions list**: Each with name, opening hours per day, and must_visit flag
2. **Distance matrix**: Travel times (in minutes) between all locations — these are RAW actual travel times
3. **Schedule constraints**: Day 0 arrival info, last day deadline, hotels per night, pace, mobility_plan_overview

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
- The distance matrix gives RAW travel times. Add a FLEXIBLE buffer based on context:
  - Traffic, parking, walking to/from transport
  - Flexibility if the previous stop runs late or early
  - Making the schedule easy to read and remember (clean round times)
- **Buffer is FLEXIBLE — adapt to context, not a fixed formula**:
  - Same neighborhood (≤5 min raw in travel times matrix): 5-10 min gap is fine. Don't inflate short walks.
  - Moderate distance (5-30 min raw in travel times matrix): add ~10-15 min buffer. Use smaller buffers within the same district, larger when crossing areas.
  - Long distance (>30 min raw in travel times matrix): add ~15-20 min buffer for traffic unpredictability.
  - The KEY is: buffer should feel NATURAL for each specific transition, not a uniform rule.
- Round arrival times to multiples of 15 minutes (09:00, 09:15, 09:30, 09:45) for a clean, easy-to-follow schedule
- Group geographically close attractions on the same day (use travel times to determine proximity)

### Opening Hours & Hotel
- Respect opening hours: arrival ≥ opening time, departure ≤ closing time
- If you would arrive at an attraction BEFORE it opens, try to rearrange the order, visit somewhere else first, or start the day later. Small waits (≤15 min) are acceptable but avoid scheduling long idle waits.
- You decide daily start and end times based on the pace, logistics, and what feels natural
- On the first day, consider arrival time — travelers may need to drop luggage, rest, etc.
- On the last day, respect the hard deadline for departure (flight or transport)
- Read **mobility_plan_overview** in constraints — it describes the trip's logistics. Use it to decide how the day flows naturally.

### Climate & Context-Aware Scheduling
Consider the destination's characteristics when scheduling:
- **Hot tropical cities** (Ho Chi Minh City, Da Nang, Bangkok, etc.): Avoid scheduling outdoor attractions during peak heat (12:00-15:00). Prefer: morning outdoor → lunch → rest/check-in → late afternoon/evening outdoor.
- **Cool/temperate destinations** (Da Lat, Sa Pa, Hanoi in winter): Afternoon outdoor is fine; no need to avoid midday.
- **Rainy season**: Bundle outdoor attractions in the morning when rain is less likely.
- Think about what a LOCAL would do — in a hot city, nobody walks around sightseeing at 13:30 under the sun after lunch. They rest, sit in a café, or handle indoor tasks (like hotel check-in).
- After a long meal, travelers naturally want to relax briefly — don't rush them into the next outdoor attraction immediately.

### Accommodation & Luggage
Check `accommodation_context` in constraints:
- **If `type` == "home"**: The traveler is staying at their own home. DO NOT schedule `check_in` or `check_out` roles. They can return home to `rest` at literally ANY time they want without waiting for a specific room availability time. Use `start_day` and `end_day` for their home.
- **If `type` == "hotel"**: Hotel check-in/check-out times are provided in the `hotels` constraints. Use them naturally:

- **check_in**: The traveler formally checks into the hotel room. Can only happen AT or AFTER the hotel's check_in_time.
- **check_out**: The traveler checks out of the hotel room. Must happen BEFORE the hotel's check_out_time.
- **luggage_drop**: Drop luggage at hotel reception BEFORE check-in time (room not ready yet). If arriving AFTER check-in time, just use check_in — no separate luggage_drop needed.
- **luggage_pickup**: Pick up stored luggage from hotel. Needed when travelers checked out earlier but still had time to explore before departing.

**IMPORTANT — Check-in scheduling priority:**
When lunch ends and the hotel check-in time is approaching (within ~60 min), DO NOT squeeze in a short outdoor activity just to fill time. Instead:
- **Extend the meal slightly** if the gap is small (e.g., lunch 12:00-13:30, check-in at 14:00 → extend lunch to 14:00 or add a short walk/café stop, then check-in)
- **Go directly to hotel** for check-in + rest, then explore refreshed in the late afternoon
- This is especially important in hot climates where early afternoon is the worst time for outdoor sightseeing

**IMPORTANT — Avoid unnecessary hotel round-trips:**
Do NOT schedule a mid-day detour BACK to the hotel just for check-in. Travelers should not ping-pong between hotel and attractions. Instead, fold check-in into a natural break in the day.

Think about it naturally:
- Arrive early morning by flight → hotel → luggage_drop → explore nearby → lunch → check_in + rest (combine naturally after lunch, room is ready by then) → afternoon/evening exploring
- Arrive late morning by flight → hotel → luggage_drop → lunch nearby → check_in + rest → afternoon exploring
- Arrive afternoon (after check-in time) → hotel → check_in directly → rest if needed → evening exploring
- Arrive late evening → hotel → check_in → end_day (explore starts next morning)
- Last day, flight in afternoon → check_out morning → lunch → airport
- Last day, flight late evening → check_out morning → explore → luggage_pickup → airport
- Road trip (motorbike/car) → luggage stays in vehicle → no luggage_drop/luggage_pickup needed. Just check_in when arriving at hotel in the evening, check_out when leaving in the morning.

**Arrival day by flight/train/coach**: Travelers have already spent hours in transit. They are tired. The natural rhythm is: handle luggage → maybe explore a bit if arrived early → eat → check_in + rest → then continue with a lighter afternoon/evening. Do NOT pack the arrival day as heavily as a normal day.

The `luggage_context` in constraints tells you whether luggage management is needed for this trip.

### Rest
- **rest**: Resting at the accommodation. Can be a midday nap, afternoon break, or evening rest before going out again. If `accommodation_context.type` == "hotel", rest is only possible when the room is available (after check_in, before check_out). If `accommodation_context.type` == "home", rest is possible ANY time.
- Duration depends on context: ~60-90 min for a quick recharge, ~90-120 min if travelers had a long flight or early morning.
- Use rest when the schedule naturally calls for it — don't force it. On a packed-pace trip, rest can be skipped entirely. On a relaxed trip, rest makes the day more enjoyable.
- Rest is most natural right after check_in: `["check_in", "rest"]` as one combined stop.


### Meals — MANDATORY
- Lunch MUST START between 11:00-13:00 (duration: 60-90 min, flexible based on context). Dinner MUST START between 18:00-20:00 (duration: 60-90 min).
- **Meal duration is FLEXIBLE**: Extend to ~90 min when there's a natural gap to fill (e.g., waiting for check-in time), or shorten to ~60 min when the schedule is tight. The goal is a natural rhythm, not a fixed block.
- Meals are NOT optional. Every day MUST have lunch AND dinner unless:
  - **Skip lunch ONLY IF** the day starts AFTER 13:00 (e.g., flight arrives at 15:00)
  - **Skip dinner ONLY IF** the day ends BEFORE 18:00 (e.g., flight departs at 16:00)
- DO NOT replace a meal with an attraction. If it's meal time, schedule the meal.
- DO NOT schedule an attraction visit that overlaps with meal windows. If it's about lunch time (example: 11:00), go eat — don't start an attraction visit.
- When approaching a meal window, finish the current attraction first, then eat, then continue.
- **Meal distance rule**: Restaurants are found near each meal location AFTER scheduling, so assume meals happen near the previous attraction:
  - Previous stop (A) → meal: travel is ~15 min (walk to nearby restaurant)
  - Meal → next stop (B): travel = same as A → B from the distance matrix (restaurant is near A)
- **Meal Notes**: You MUST add a `note` for each meal stop describing the context naturally in the requested language. Do NOT just leave it empty.

### Includes (Sub-attractions)
- Some attractions have an "includes" field listing sub-attractions that are WITHIN or ADJACENT to them (e.g., Hoan Kiem Lake includes Ngoc Son Temple)
- The suggested_duration_minutes already covers all included sub-attractions
- In your output, add an "includes" field to each attraction stop listing which included sub-places you recommend visiting at that stop
- Not all includes need to be visited — choose based on available time, traveler interest, and pace
- If an attraction has no includes, set "includes" to an empty list []

### Adding & Dropping
- You MAY adjust visit durations — the suggested duration is a guide, not mandatory
- **Dropping stops**: You MAY drop non-must-visit attractions if the schedule is too packed. must_visit attractions MUST appear in the schedule. It's BETTER to drop some places and have a relaxing trip than to rush through everything.
- **Adding activities**: If a day has gaps of 2+ hours with nothing to do, you MUST either rearrange the schedule to eliminate the gap OR suggest additional activities to fill it. Be CREATIVE but reasonable — activities can include: exploring local neighborhoods, visiting a café or tea house, checking out local markets, strolling through parks, trying street food, browsing souvenir shops, visiting a specific landmark you know about, or relaxing at a scenic viewpoint. Add these as stops with role ["generic"] and a reasonable duration. Use specific, vivid names that describe the actual activity — e.g., "Cà phê Trứng tại phố cổ", "Dạo chợ Đêm Hà Nội", "Ngồi nghỉ ven Hồ Xuân Hương", "Khám phá khu phố cổ". The "generic" role is ONLY for activities YOU suggest that are NOT in the input attractions list.
- If souvenir shopping seems appropriate (based on mobility_plan_overview context and the attraction being near markets, cultural sites, or tourist areas), add a brief note about what souvenirs to buy there using the `"note"` field on that attraction stop. Example: "Mua quà lưu niệm tranh Đông Hồ và đồ thủ công mỹ nghệ tại đây."

### Weather-Aware Scheduling
If a **Daily Weather Forecast** is provided in the input, use it to make smarter scheduling decisions:
- **Hot days**: After lunch, consider scheduling a rest at the hotel or an indoor activity instead of outdoor attractions. Schedule outdoor attractions for the cooler morning (before 11:00) or late afternoon (after 15:00).
- **Rainy days**: Prioritize indoor attractions. Move weather-sensitive outdoor attractions to drier days if possible.
- **Cool/pleasant days**: These are the best for outdoor exploration — pack more outdoor attractions on these days.
- **General principle**: The schedule should feel comfortable and realistic for travelers. Don't force people to walk outdoors in scorching heat or heavy rain when there are indoor alternatives available.
- **If no weather data is available**: Schedule normally with your own weather awareness about the destination at that time of year.

## Available Roles
The `role` field is a **LIST** of role strings. Most stops have a single role like `["attraction"]`. When multiple actions happen at the same stop, combine them: `["check_in", "luggage_drop"]` or `["check_out", "luggage_pickup"]`.

Boundary roles (arrival = departure is allowed):
- `start_day`: Daily start point (hotel). Just departing — arrival = departure.
- `end_day`: Daily end point (hotel). Just arriving — departure can be empty "".
- `outbound_arrival`: Arrival journey at destination. Applies to ALL non-local travel modes:
  - **Flight**: arrival = landing time, departure = after customs/baggage. Location = arrival airport.
  - **Coach/Train/Car/Motorbike**: This node represents the actual travel journey. Set `arrival` = the `start_time` provided in constraints for day_0_arrival. Set `departure` = the `arrival_time` provided in constraints for day_0_arrival. If `start_time` is the previous day (e.g. "22:00 -1"), you still set `arrival`="22:00 -1", the `departure` is when they arrive. Location Name MUST explicitly state the journey: "Origin → Destination" (e.g., "Bắc Ninh → Hà Nội").
  - **Local trip** (departure == destination): NO outbound_arrival needed — just use `start_day`.
- `return_departure`: Departure journey from destination back to origin. Applies to ALL non-local travel:
  - **Flight**: arrival ~ 2h BEFORE flight departure time, departure = actual flight time. Location = departure airport.
  - **Coach/Train**: This node represents the return trip. The traveler must arrive at the hub ~30 min before departure for boarding. Set `arrival` = the `deadline_time` from last_day_deadline constraints (30 min before start_time). Set `departure` = the `arrival_time` from last_day_deadline constraints. Location Name = hub name from constraints.
  - **Car/Motorbike**: This node represents the return trip. No buffer needed — just hop on and go. Set `arrival` = the `start_time` from last_day_deadline constraints. Set `departure` = the `arrival_time` from last_day_deadline constraints. Location Name MUST explicitly state the journey: "Destination → Origin" (e.g., "Hà Nội → Bắc Ninh").
  - **Local trip**: NO return_departure needed.

Hotel logistics roles:
- `check_in`: Formal hotel check-in. Must be AT or AFTER hotel's check_in_time. ~15-30 min.
- `check_out`: Formal hotel check-out. Must be BEFORE hotel's check_out_time. ~15-30 min.
- `luggage_drop`: Drop luggage at hotel BEFORE check-in time. ~15-30 min.
- `luggage_pickup`: Pick up stored luggage. ~15-30 min.
- `rest`: Rest at hotel (room must be available). ~60-120 min.

Activity roles:
- `attraction`: Tourist attraction FROM THE INPUT LIST. Visit ≥ 30 min. Has extra field `"includes": [list]`. May optionally have `"note"` for souvenir shopping hints.
- `generic`: Activity suggested by YOU (not in input). Visit ≥ 30 min.
- `lunch`: Lunch break. 60-90 min (flexible based on context).
- `dinner`: Dinner break. 60-90 min (flexible based on context).

### Combining roles
When multiple things happen at the same stop, put all roles in the list:
- Arrive after check-in time? → `["check_in", "luggage_drop"]` (one stop, luggage drop is implicit in check-in)
- Check out and leave immediately? → `["check_out", "luggage_pickup"]` (one stop)
- Check in and rest right after? → `["check_in", "rest"]` (one stop, longer duration)
- Just checking in, no rest? → `["check_in"]` alone
- Single-role stops: `["attraction"]`, `["lunch"]`, `["rest"]`, etc.

**RULE: If two consecutive stops have the SAME name, you MUST merge them into ONE stop with all roles combined.** Never output two separate stops at the same location back-to-back. For example, do NOT output a `["check_in"]` stop at Hotel X followed immediately by a `["rest"]` stop at Hotel X — merge them into one `["check_in", "rest"]` stop.

## Response Format
CRITICAL: Output ONLY a raw JSON object. No text before or after. No markdown fences.

Each stop needs: `name`, `role` (LIST of strings), `arrival` (HH:MM), `departure` (HH:MM).
Attraction stops also need: `includes` (list). Optionally `note` for souvenir hints.
Do NOT include duration, minutes, or travel time fields — the validator computes these automatically.
Each day MUST have a `title` field: a short, descriptive title for the day (e.g., "Khám phá phố cổ Hà Nội", "Bay đến & Nhận phòng", "Ngày cuối - Mua sắm & Về"). Write the title in the user's language.

### `note` field — contextual annotations for special stops
Add a `"note"` field (string, 1-2 short sentences) to provide extra context. **Write ALL notes in {language} (the user's preferred language).**

**MUST generate notes for these roles:**
- `outbound_arrival` / `return_departure`: Summarize the transport info from constraints. MUST include: transport mode, vehicle number/airline, departure location + time, and arrival location + time. Example: "Chuyến bay VN123, Vietnam Airlines. Khởi hành 07:00 từ SGN, đến HAN lúc 09:00."
- `check_in` / `check_out`: Mention the hotel timing info. Example: "Nhận phòng từ 14:00." or "Trả phòng trước 12:00."
- `luggage_drop` / `luggage_pickup`: Briefly explain the context. Example: "Gửi hành lý tại khách sạn trước khi nhận phòng."
- `rest` / `end_day`: Briefly describe the relaxation. Example: "Nghỉ ngơi tại khách sạn." hoặc "Về khách sạn nghỉ ngơi qua đêm."

**IMPORTANT - Multiple Roles:** If a stop combines multiple roles (e.g., `["check_in", "rest"]` or `["check_out", "luggage_pickup"]`), you MUST combine their meanings into a single note. Example: "Nhận phòng từ 14:00 và nghỉ ngơi tại khách sạn." or "Trả phòng trước 12:00 và gửi lại hành lý tại lễ tân."

{
    "days": [
        {
            "day": 0,
            "title": "Đến Hà Nội & Khám phá",
            "stops": [
                {
                    "name": "Noi Bai International Airport",
                    "role": ["outbound_arrival"],
                    "arrival": "09:00",
                    "departure": "09:30",
                    "note": "Flight VN123, Vietnam Airlines. Departs 07:00 SGN → arrives 09:00 HAN."
                },
                {
                    "name": "Hotel X",
                    "role": ["luggage_drop"],
                    "arrival": "10:15",
                    "departure": "10:45",
                    "note": "Gửi hành lý tại khách sạn trước khi đi chơi."
                },
                {
                    "name": "Temple of Literature",
                    "role": ["attraction"],
                    "includes": [],
                    "arrival": "11:00",
                    "departure": "12:30",
                    "note": "Mua quà lưu niệm tranh thủ bút và đồ thủ công mỹ nghệ."
                },
                {
                    "name": "Lunch",
                    "role": ["lunch"],
                    "arrival": "12:45",
                    "departure": "14:15"
                },
                {
                    "name": "Hotel X",
                    "role": ["check_in", "rest"],
                    "arrival": "14:15",
                    "departure": "15:30",
                    "note": "Nhận phòng khách sạn từ 14:00 và nghỉ trưa."
                },
                {
                    "name": "Ho Chi Minh Mausoleum",
                    "role": ["attraction"],
                    "includes": ["One Pillar Pagoda"],
                    "arrival": "15:00",
                    "departure": "16:30"
                },
                {
                    "name": "Dinner",
                    "role": ["dinner"],
                    "arrival": "18:00",
                    "departure": "19:30"
                },
                {
                    "name": "Hotel X",
                    "role": ["end_day"],
                    "arrival": "19:45",
                    "departure": "",
                    "note": "Về khách sạn nghỉ ngơi qua đêm."
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
- `role` is ALWAYS a list of strings, even for single roles: `["attraction"]`, NOT `"attraction"`
- For intermediate stops: departure MUST be AFTER arrival (you spend time there)
- For `start_day`: arrival = departure (you just leave)
- For `end_day`: departure = "" (you just arrive for the night)
- The gap between one stop's departure and the next stop's arrival must be enough for the raw travel time (with buffer added)
- If two consecutive stops are at the SAME location (e.g., hotel → check_in at same hotel), the next arrival can equal the current departure (no travel needed)
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

    import re
    
    raw = hours_str.strip().replace("(assumed)", "").strip()
    raw = raw.replace('\u2013', '-').replace('\u2014', '-')

    ranges = [r.strip() for r in raw.split(",")]
    earliest, latest = 1440, 0

    def parse_time_part(t_str: str, ampm_fallback: str = "") -> int:
        t_str = t_str.strip().lower()
        is_pm = 'pm' in t_str or ampm_fallback == 'pm'
        is_am = 'am' in t_str or ampm_fallback == 'am'
        t_clean = re.sub(r'[a-z\s]+', '', t_str)
        if not t_clean: return 0
        parts = t_clean.split(':')
        h = int(parts[0]) if parts[0] else 0
        m = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        if is_pm and h < 12:
            h += 12
        elif is_am and h == 12:
            h = 0
        return h * 60 + m

    for r in ranges:
        parts = r.split("-")
        if len(parts) != 2:
            continue
        
        start_str, end_str = parts[0].strip(), parts[1].strip()
        end_lower = end_str.lower()
        ampm_fallback = "pm" if "pm" in end_lower else ("am" if "am" in end_lower else "")
        
        try:
            o = parse_time_part(start_str, ampm_fallback)
            c = parse_time_part(end_str, ampm_fallback)
            # handle cases like "08:00 AM - 08:00 PM" where the AM is explicit on start
            if "am" in start_str.lower():
                o = parse_time_part(start_str, "am")
            
            if c > o:
                earliest = min(earliest, o)
                latest = max(latest, c)
            elif c < o:  # wraps around midnight (e.g. 5:00 PM - 2:00 AM)
                earliest = min(earliest, o)
                latest = 1440
        except (ValueError, IndexError):
            continue

    return (earliest, latest) if earliest < latest or earliest < 1440 else None


def _validate_schedule(
    schedule: dict,
    attractions_info: list[dict],
    schedule_constraints: dict | None = None,
    distance_pairs: list[dict] | None = None,
) -> list[dict]:
    """
    Validate LLM schedule against all constraints.
    All arithmetic is done by code — LLM only provides arrival/departure HH:MM.
    Role is a LIST of strings (e.g., ["check_in", "luggage_drop"]).

    Checks:
    1. Travel feasibility: gap between stops >= raw travel time
    2. Opening hours (attractions only)
    3. Hotel check-out timing (check_out role must be before hotel checkout time)
    4. Last day deadline
    5. Must-visit attractions present
    6. Check-in timing (check_in role must be at/after hotel check-in time)
    7. Intermediate stops: departure > arrival (positive duration)
    8. Mandatory meals (lunch/dinner)
    9. Mandatory daily start/end structure
    10. Reasonable duration (attraction >= 30min, meal >= 45min)
    11. Rest only after check_in (room must be available)

    Returns list of violation dicts.
    """
    violations = []
    constraints = schedule_constraints or {}
    attr_hours = {info["name"]: info["opening_hours"] for info in attractions_info}

    def _get_roles(stop: dict) -> set[str]:
        """Extract roles as a set from stop. Handles both list and legacy string format."""
        role = stop.get("role", [])
        if isinstance(role, str):
            return {role}
        if isinstance(role, list):
            return set(role)
        return set()

    def _has_role(stop: dict, role_name: str) -> bool:
        return role_name in _get_roles(stop)

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
            if _has_role(stop, "attraction"):
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

    # --- Track check_in across days (for rest validation) ---
    checked_in = False  # Becomes True once check_in appears in any day

    # --- Per-day checks ---
    for day_data in schedule.get("days", []):
        day_idx = day_data.get("day", 0)
        stops = day_data.get("stops", [])

        effective_location = ""  # last non-meal stop name for meal distance rule

        for stop_idx, stop in enumerate(stops):
            name = stop.get("name", "")
            roles = _get_roles(stop)
            arrival_str = stop.get("arrival", "")
            departure_str = stop.get("departure", "")

            # Parse times (code does all arithmetic)
            arrival_min = _time_to_minutes(arrival_str)
            departure_min = _time_to_minutes(departure_str) if departure_str else arrival_min
            duration = departure_min - arrival_min

            # --- Check 7: Intermediate stops must have positive duration ---
            intermediate_roles = {"attraction", "generic", "lunch", "dinner", "rest",
                                  "luggage_drop", "luggage_pickup", "check_in", "check_out"}
            if roles & intermediate_roles:
                if duration <= 0:
                    violations.append({
                        "day": day_idx, "stop_name": name,
                        "issue": f"Roles {sorted(roles)} must have departure AFTER arrival, but arrival={arrival_str} departure={departure_str}",
                    })

            # --- Check 10: Reasonable duration ---
            if roles & {"attraction", "generic"} and 0 < duration < 30:
                violations.append({
                    "day": day_idx, "stop_name": name,
                    "issue": f"Visit duration is only {duration}min (arrival={arrival_str}, departure={departure_str}). Minimum recommended: 30min.",
                })
            if roles & {"lunch", "dinner"} and 0 < duration < 45:
                violations.append({
                    "day": day_idx, "stop_name": name,
                    "issue": f"Meal duration is only {duration}min (arrival={arrival_str}, departure={departure_str}). Minimum recommended: 45min.",
                })

            # --- Check 1: Travel feasibility (gap >= raw travel time) ---
            if stop_idx > 0:
                prev_stop = stops[stop_idx - 1]
                prev_roles = _get_roles(prev_stop)
                prev_name = prev_stop.get("name", "")
                prev_dep_str = prev_stop.get("departure", "")
                prev_dep_min = _time_to_minutes(prev_dep_str) if prev_dep_str else _time_to_minutes(prev_stop.get("arrival", ""))

                gap = arrival_min - prev_dep_min

                # Determine required travel time using meal distance rule
                if roles & {"lunch", "dinner"}:
                    # A -> meal: ~15 min walk to nearby restaurant
                    required = 15
                elif prev_roles & {"lunch", "dinner"}:
                    # meal -> B: same as effective_location -> B (restaurant is near prev attraction)
                    if effective_location == name:
                        required = 0
                    else:
                        required = raw_lookup.get((effective_location, name), 0)
                elif prev_name == name:
                    # Same location (e.g., hotel -> check_in at same hotel)
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
            if "attraction" in roles:
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

            # --- Check 3: Hotel check-out timing ---
            if "check_out" in roles and day_idx in hotel_checkout_map:
                co_hotel_name, co_time_min = hotel_checkout_map[day_idx]
                if departure_min > co_time_min:
                    violations.append({
                        "day": day_idx, "stop_name": name,
                        "issue": f"Check-out departure at {departure_str} but hotel check-out deadline is {co_time_min//60:02d}:{co_time_min%60:02d}",
                    })

            # Legacy: start_day on check-out day must also respect checkout time
            if "start_day" in roles and "check_out" not in roles and day_idx in hotel_checkout_map:
                co_hotel_name, co_time_min = hotel_checkout_map[day_idx]
                if departure_min > co_time_min:
                    violations.append({
                        "day": day_idx, "stop_name": name,
                        "issue": f"Departs hotel at {departure_str} but check-out time is {co_time_min//60:02d}:{co_time_min%60:02d}",
                    })

            # --- Check 6: Check-in timing ---
            if "check_in" in roles:
                checked_in = True
                if day_idx in hotel_checkin_map:
                    ci_hotel_name, ci_time_min = hotel_checkin_map[day_idx]
                    if arrival_min < ci_time_min:
                        violations.append({
                            "day": day_idx, "stop_name": name,
                            "issue": f"Check-in at {arrival_str} but hotel check-in time is {ci_time_min//60:02d}:{ci_time_min%60:02d}. Room not available yet.",
                        })

            # --- Check 11: Rest only after check_in (unless staying at home) ---
            acc_type = constraints.get("accommodation_context", {}).get("type", "hotel")
            if "rest" in roles and not checked_in and acc_type != "home":
                violations.append({
                    "day": day_idx, "stop_name": name,
                    "issue": f"Rest at hotel but no check_in has occurred yet. Room not available.",
                })

            # --- Check 12: Consecutive stops with same name must be merged ---
            if stop_idx > 0:
                prev_stop = stops[stop_idx - 1]
                prev_name = prev_stop.get("name", "")
                if prev_name == name:
                    violations.append({
                        "day": day_idx, "stop_name": name,
                        "issue": f"Consecutive stops at '{name}' must be MERGED into one stop with combined roles. Merge the roles into a single stop.",
                    })

            # Track check_out — room no longer available after
            if "check_out" in roles:
                checked_in = False

            # Track effective location (for meal distance rule)
            if not (roles & {"lunch", "dinner"}):
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
            # Collect all roles across all stops in this day
            all_roles_in_day = set()
            for s in stops:
                all_roles_in_day.update(_get_roles(s))

            # Lunch required if schedule spans past 13:00
            if first_dep_min < 780 and last_arr_min > 780:
                if "lunch" not in all_roles_in_day:
                    violations.append({
                        "day": day_idx, "stop_name": "Lunch",
                        "issue": f"Day {day_idx} has activity before 13:00 and after 13:00 but NO lunch scheduled",
                    })

            # Dinner required if schedule spans past 18:00
            if first_dep_min < 1080 and last_arr_min > 1080:
                if "dinner" not in all_roles_in_day:
                    violations.append({
                        "day": day_idx, "stop_name": "Dinner",
                        "issue": f"Day {day_idx} has activity after 18:00 but NO dinner scheduled",
                    })

        # --- Check 9: Mandatory daily start/end structure ---
        if stops:
            first_roles = _get_roles(stops[0])
            last_roles = _get_roles(stops[-1])
            is_first_day = (day_idx == 0)
            is_last_day = (last_day_idx is not None and day_idx == last_day_idx)

            if is_first_day:
                if not (first_roles & {"outbound_arrival", "start_day"}):
                    violations.append({
                        "day": day_idx, "stop_name": stops[0].get("name", ""),
                        "issue": f"Day 0 must START with 'outbound_arrival' or 'start_day', got {sorted(first_roles)}",
                    })
            else:
                if "start_day" not in first_roles:
                    violations.append({
                        "day": day_idx, "stop_name": stops[0].get("name", ""),
                        "issue": f"Day {day_idx} must START with 'start_day' (hotel), got {sorted(first_roles)}",
                    })

            if is_last_day:
                if not (last_roles & {"return_departure", "end_day"}):
                    violations.append({
                        "day": day_idx, "stop_name": stops[-1].get("name", ""),
                        "issue": f"Last day must END with 'return_departure' or 'end_day', got {sorted(last_roles)}",
                    })
            else:
                if "end_day" not in last_roles:
                    violations.append({
                        "day": day_idx, "stop_name": stops[-1].get("name", ""),
                        "issue": f"Day {day_idx} must END with 'end_day' (return to hotel), got {sorted(last_roles)}",
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
            weather_data = agent_outputs.get("weather", {})
            human_content = _build_scheduling_prompt(pipeline_data, plan_context, weather_data)

            # Inject language into system prompt for note generation
            language = plan_context.get("language", "en")
            system_content = ITINERARY_SCHEDULER_SYSTEM.replace("{language}", language)

            messages = [
                SystemMessage(content=system_content),
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

def _build_scheduling_prompt(pipeline_data: dict, plan_context: dict, weather_data: dict | None = None) -> str:
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
    sections.append(f"- Language: {plan_context.get('language', 'en')} (use this for all notes and generic activity names)")

    # Day 0 arrival
    arrival = constraints.get("day_0_arrival")
    if arrival:
        sections.append(f"\n### Day 0 Arrival")
        sections.append(f"- Location: {arrival.get('location', '?')}")
        if arrival.get("start_time"):
            sections.append(f"- Route Start Time: {arrival['start_time']}")
        sections.append(f"- Arrival time: {arrival.get('arrival_time', '?')}")
        if arrival.get("flight_number"):
            sections.append(f"- Flight: {arrival.get('flight_number', '')} ({arrival.get('airline', '')})")
            sections.append(f"- Departure: {arrival.get('departure_airport', '')} at {arrival.get('departure_time', '')}")
        if arrival.get("ready_time"):
            sections.append(f"- Ready to explore: {arrival['ready_time']}")
        sections.append(f"- Note: {arrival.get('note', '')}")

    # Last day deadline
    deadline = constraints.get("last_day_deadline")
    if deadline:
        sections.append(f"\n### Last Day Deadline (HARD CONSTRAINT)")
        dl_mode = deadline.get("mode", "")
        if dl_mode:
            sections.append(f"- Mode: {dl_mode}")
        if deadline.get("location"):
            sections.append(f"- Must be at: {deadline.get('location')}")
        if deadline.get("deadline_time"):
            sections.append(f"- Deadline (must arrive by): {deadline.get('deadline_time')}")
        if deadline.get("start_time"):
            sections.append(f"- Route Start Time: {deadline.get('start_time')}")
            sections.append(f"- Route Arrival Time: {deadline.get('arrival_time', '?')}")
        if deadline.get("flight_number"):
            sections.append(f"- Return flight: {deadline.get('flight_number', '')} ({deadline.get('airline', '')})")
            sections.append(f"- Flight departs: {deadline.get('flight_departure', '')} → arrives {deadline.get('arrival_airport', '')} at {deadline.get('arrival_time', '')}")
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

    # Luggage context
    luggage_ctx = constraints.get("luggage_context", {})
    if luggage_ctx:
        sections.append(f"\n### Luggage Context")
        sections.append(f"- Needs luggage management: {luggage_ctx.get('needs_luggage_management', False)}")
        sections.append(f"- {luggage_ctx.get('note', '')}")

    # Mobility plan overview
    if constraints.get("mobility_plan_overview"):
        sections.append(f"\n### Trip Logistics Overview")
        sections.append(constraints["mobility_plan_overview"])

    # Weather forecast
    if weather_data and weather_data.get("daily"):
        sections.append(f"\n### Daily Weather Forecast")
        sections.append("Use this to optimize scheduling: prefer indoor/shaded activities during hot midday, avoid outdoor attractions in heavy rain, etc.")
        for day_w in weather_data["daily"]:
            rain = f", rain chance: {day_w['rain_chance_pct']}%" if 'rain_chance_pct' in day_w else ""
            sections.append(
                f"- Day {day_w['day']} ({day_w.get('date', '?')}, {day_w.get('day_of_week', '?')}): "
                f"{day_w.get('condition', '?')}, {day_w.get('temp_min', '?')}–{day_w.get('temp_max', '?')}°C, "
                f"humidity: {day_w.get('humidity', '?')}%{rain}"
            )
        if weather_data.get("outside_range_note"):
            sections.append(f"Note: {weather_data['outside_range_note']}")

    sections.append("\nCreate the optimized schedule now. Output ONLY the JSON.")

    return "\n".join(sections)
