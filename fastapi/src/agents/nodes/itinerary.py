"""
Itinerary Agent Node.

Uses LLM to schedule attractions.
Receives distance matrix + opening hours + soft constraints from itinerary_builder,
then prompts the LLM to arrange the multi-day schedule.

Includes a validation loop that checks time-window violations and re-prompts
the LLM up to 2 times if violations are found.
"""

import json
import logging
import re
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.agents.state import GraphState
from src.services.itinerary_builder import run_itinerary_pipeline
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.config import settings

logger = logging.getLogger(__name__)

useRouteMatrix = settings.USE_ROUTE_MATRIX

# USE_VERCEL_AI_GATEWAY = True

llm_itinerary = (
    ChatOpenAI(
        model=settings.MODEL_NAME,
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    # if USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model=settings.MODEL_NAME,
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_ITINERARY or settings.GOOGLE_GEMINI_API_KEY,
        temperature=0.3,
        streaming=False,
    )
)

ITINERARY_SCHEDULER_SYSTEM = """You are the Itinerary Scheduling Agent. You receive a list of attractions with opening hours, a distance matrix between all locations, and schedule constraints. Your job is to arrange them into a natural, optimized multi-day travel schedule.

## Input You Receive
1. **Attractions list**: Each with name, opening hours per day, and must_visit flag
2. **Distance matrix**: Travel times (in minutes) between all locations — these are RAW actual travel times
3. **Schedule constraints**: Day 1 arrival info, last day deadline, hotels per night, pace, mobility_plan_overview

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
- On the first day (day 1), consider arrival time — travelers may need to drop luggage, rest, etc.
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

**IMPORTANT — Check-in scheduling priority (CRUCIAL RULE!):**
When a meal (like lunch) ends and the hotel check-in time is approaching (e.g., lunch ends at 13:00 or 13:30, but check-in is at 14:00), **NEVER squeeze an attraction into that small intermediate gap**. Adding an attraction visit right before check-in, especially after a flight or at midday, is exhausting and completely illogical.
Instead, you MUST do one of the following to bridge the gap naturally:
1. **Extend the meal's duration**: Simply make the lunch `departure` match the time you need to leave for the hotel. It is perfectly fine to have a 1.5 to 2-hour lunch to relax at the restaurant before heading to the hotel.
2. **Add a `generic` leisure stop**: Schedule a 15-30 min coffee break or relaxation stop.
3. **Just extend gap between meal and check-in**: lunch ends at 13:30 but go to hotel just 15 minutes -> add 15 minutes gap between meal and check-in so arrival to check-in hotel at 14:00.
**DO NOT** schedule sightseeing attractions (`attraction`) during this pre-check-in midday gap.

**IMPORTANT — Avoid unnecessary hotel round-trips:**
Do NOT schedule a mid-day detour BACK to the hotel just for check-in if travelers are already far away doing activities. However, if they just arrived from the airport/station, the natural flow is going to the hotel first, having lunch, checking in, and then starting to explore.

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
- **IMPORTANT**: When an attraction HAS includes, you MUST add a `note` describing specifically which sub-attractions to visit, and if some are skipped, mention them as optional extras. Example: "Visit the Mausoleum and Ho Chi Minh Stilt House. If time permits, also stop by One Pillar Pagoda nearby."

### Adding & Dropping
- You MAY adjust visit durations — the suggested duration is a guide, not mandatory
- **Dropping stops**: You MAY drop non-must-visit attractions if the schedule is too packed. must_visit attractions MUST appear in the schedule. It's BETTER to drop some places and have a relaxing trip than to rush through everything.
- **Adding activities (CRITICAL — NO EMPTY GAPS)**: NEVER leave gaps of 1.5+ hours with nothing to do (unless user want it). If a day has a gap, you MUST either rearrange the schedule to eliminate it OR add generic activities to fill it. Be CREATIVE but reasonable — activities can include: exploring local neighborhoods, visiting a café or tea house, checking out local markets, strolling through parks, trying street food, browsing souvenir shops, visiting a specific landmark you know about, or relaxing at a scenic viewpoint. Add these as stops with role ["generic"] and a reasonable duration. Use specific, vivid names that describe the actual activity — e.g., "Egg coffee in the Old Quarter", "Night Market stroll", "Lakeside relaxation". The "generic" role is ONLY for activities YOU suggest that are NOT in the input attractions list.
- If souvenir shopping seems appropriate (based on mobility_plan_overview context and the attraction being near markets, cultural sites, or tourist areas), add a brief note about what souvenirs to buy there using the `"note"` field on that attraction stop. Example: "Buy Dong Ho folk paintings and handcrafted souvenirs here."

### Weather-Aware Scheduling
If a **Daily Weather Forecast** is provided in the input, use it to make smarter scheduling decisions:
- **Hot days**: After lunch, consider scheduling a rest at the hotel or an indoor activity instead of outdoor attractions. Schedule outdoor attractions for the cooler morning (before 11:00) or late afternoon (after 15:00).
- **Rainy days**: Prioritize indoor attractions. Move weather-sensitive outdoor attractions to drier days if possible.
- **Cool/pleasant days**: These are the best for outdoor exploration — pack more outdoor attractions on these days.
- **General principle**: The schedule should feel comfortable and realistic for travelers. Don't force people to walk outdoors in scorching heat or heavy rain when there are indoor alternatives available.
- **If no weather data is available**: Schedule normally with your own weather awareness about the destination at that time of year.

### Travel Style Intelligence
Read the `mobility_plan_overview` carefully to understand the trip structure. Different travel styles require VERY different daily rhythms:

- **Road trip / Loop route** (e.g., Ha Giang loop, coastal highway): Travelers are ON THE ROAD all day. Attractions are spread along the route, visited sequentially. Lunch happens at a stop along the way. DO NOT schedule midday hotel rest — they won't be near a hotel until evening. The natural pattern is: depart morning → drive + stop at attractions along the route → eat lunch wherever they are → continue → arrive at next overnight stop in evening.
- **City exploration** (e.g., staying in Hanoi, walking around): Hub-and-spoke style. Hotel is nearby. Midday rest or check-in is natural after lunch, especially in hot weather.
- **Mixed trips** (e.g., 2 days in Hanoi + 3 days Ha Giang loop): Analyze EACH DAY independently. City days can include hotel rest; road trip days should not.

Do NOT apply rigid rules. Analyze the mobility_plan_overview and each day's context to decide whether midday rest makes sense. Even on a road trip, if the day's destinations are all in one town (not moving to the next town), a rest could be appropriate.

## Available Roles
The `role` field is a **LIST** of role strings. Most stops have a single role like `["attraction"]`. When multiple actions happen at the same stop, combine them: `["check_in", "luggage_drop"]` or `["check_out", "luggage_pickup"]`.

Boundary roles (arrival = departure is allowed):
- `start_day`: Daily start point (hotel). Just departing — arrival = departure.
- `end_day`: Daily end point (hotel). Just arriving — departure can be empty "".
- `outbound_arrival`: Arrival journey at destination. Applies to ALL non-local travel modes:
  - **Flight**: This stop represents the ENTIRE flight journey. Set `arrival` = flight departure time from origin (boarding), `departure` = flight landing time at destination + ~30 min (luggage/customs only — travel to next stop is handled separately by distance matrix). Location = arrival airport. Example: flight departs 07:00, lands 09:00 → arrival=07:00, departure=09:30.
  - **Coach/Train/Car/Motorbike**: This node represents the actual travel journey. Set `arrival` = the `start_time` provided in constraints for day_0_arrival (keep the "-1" suffix if present — e.g., "20:00 -1"). Set `departure` = the time travelers are READY TO START the day (after arriving + getting settled). Location = the exact `location` name provided in constraints for day_0_arrival.
    - The note MUST clearly state: departure time from origin, arrival time at destination, and what time the day begins. Example note: "Xe khách xuất phát lúc 22:00 tối hôm trước, đến Hà Giang lúc 05:00 sáng. Làm thủ tục thuê xe máy, bắt đầu hành trình lúc 07:00."
  - **Local trip** (departure == destination): NO outbound_arrival needed — just use `start_day`.
- `return_departure`: Departure journey from destination back to origin. Applies to ALL non-local travel:
  - **Flight**: This stop represents the ENTIRE return flight journey. Set `arrival` = ~2h BEFORE flight departure time (airport check-in), `departure` = flight arrival time at origin. Location = departure airport. Example: flight departs 18:00, arrives 20:00 → arrival=16:00, departure=20:00.
  - **Coach/Train**: This node represents the return trip. Set `arrival` = the `deadline_time` from last_day_deadline constraints (30 min before start_time). Set `departure` = the `arrival_time` from last_day_deadline constraints. Location = the exact `location` name provided in last_day_deadline constraints.
    - **Overnight return (arrival_time is next day)**: If the return journey arrives the next day, append "+1" to the departure time: e.g., `departure: "05:00 +1"`. The note MUST clearly state the travel schedule.
    - **Same-day return**: Just set departure = arrival_time as-is.
  - **Car/Motorbike**: This node represents the return trip. No buffer needed — just hop on and go. Set `arrival` = the `start_time` from last_day_deadline constraints. Set `departure` = the `arrival_time` from last_day_deadline constraints. Location = the exact `location` name provided in last_day_deadline constraints.
  - **Local trip**: NO return_departure needed.

Hotel logistics roles:
- `check_in`: Formal hotel check-in. Must be AT or AFTER hotel's check_in_time. ~15-30 min.
- `check_out`: Formal hotel check-out. Must be BEFORE hotel's check_out_time. ~15-30 min.
- `luggage_drop`: Drop luggage at hotel BEFORE check-in time. ~15-30 min.
- `luggage_pickup`: Pick up stored luggage. ~15-30 min.
- `rest`: Rest at hotel (room must be available). ~60-120 min.

Activity roles:
- `attraction`: Tourist attraction FROM THE INPUT LIST. Visit time reasonable with that attraction. Has extra field `"includes": [list]`. May optionally have `"note"` for souvenir shopping hints.
- `generic`: Activity suggested by YOU (not in input). Visit time reasonable with that generic activity.
- `lunch`: Lunch break. 60-90 min (flexible based on context).
- `dinner`: Dinner break. 60-90 min (flexible based on context).

CRITICAL ACTIVITY RULE: DO NOT schedule two meals back-to-back (e.g., lunch followed immediately by dinner). You MUST schedule at least one activity (attraction, generic, or rest) in between meals to represent the time spent.

### Combining roles
When multiple things happen at the same stop, put all roles in the list:
- Arrive after check-in time? → `["check_in", "luggage_drop"]` (one stop, luggage drop is implicit in check-in)
- Check out and leave immediately? → `["check_out", "luggage_pickup"]` (one stop)
- Check in and rest right after? → `["check_in", "rest"]` (one stop, longer duration)
- Arrive late, check in and sleep? → `["check_in", "end_day"]` (one stop — common on road trips when arriving at hotel in the evening)
- Just checking in, no rest? → `["check_in"]` alone
- Single-role stops: `["attraction"]`, `["lunch"]`, `["rest"]`, etc.

**RULE: If two consecutive stops have the SAME name, you MUST merge them into ONE stop with all roles combined.** Never output two separate stops at the same location back-to-back. For example, do NOT output a `["check_in"]` stop at Hotel X followed immediately by a `["rest"]` stop at Hotel X — merge them into one `["check_in", "rest"]` stop.

## Response Format
CRITICAL: Output ONLY a raw JSON object. No text before or after. No markdown fences.

Each stop needs: `name`, `role` (LIST of strings), `arrival` (HH:MM), `departure` (HH:MM).
Attraction stops also need: `includes` (list). Optionally `note` for souvenir hints.
Do NOT include duration, minutes, or travel time fields — the validator computes these automatically.
Each day MUST have a `title` field: a short, descriptive title for the day (e.g., "Explore Hanoi Old Quarter", "Arrival & Check-in", "Last Day - Shopping & Departure"). Write the title in the user's language.

### CRITICAL — Exact Name Rule
You MUST use the EXACT attraction and hotel names as provided in the input data. Do NOT modify, abbreviate, translate, add parentheses, or append alternative names. Copy the name character-for-character. If you want to add context (e.g., Vietnamese name, sub-attractions), put it in the `note` field instead.

### `note` field — contextual annotations for special stops
Add a `"note"` field (string, 1-2 short sentences) to provide extra context. **Write ALL notes in {language} (the user's preferred language).**

**MUST generate notes for these roles:**
- `outbound_arrival` / `return_departure`: Summarize the transport info from constraints. MUST include: transport mode, vehicle number/airline, departure location + time, and arrival location + time. Example: "Flight VN123, Vietnam Airlines. Departs 07:00 from SGN, arrives 09:00 at HAN."
- `check_in` / `check_out`: Mention the hotel timing info. Example: "Check-in from 14:00." or "Check-out before 12:00."
- `luggage_drop` / `luggage_pickup`: Briefly explain the context. Example: "Drop luggage at hotel reception before check-in time."
- `rest` / `end_day`: Briefly describe the relaxation. Example: "Rest at hotel." or "Return to hotel for overnight stay."
- `attraction` with includes: List which sub-attractions to visit, mention any skipped ones as optional. Example: "Visit the Mausoleum and Stilt House. If time permits, stop by One Pillar Pagoda nearby."

**IMPORTANT - Multiple Roles:** If a stop combines multiple roles (e.g., `["check_in", "rest"]` or `["check_out", "luggage_pickup"]`), you MUST combine their meanings into a single note. Example: "Check-in from 14:00 and rest at hotel." or "Check-out before 12:00 and leave luggage at reception."

{
    "days": [
        {
            "day": 1,
            "title": "Arrival in Hanoi & Explore",
            "stops": [
                {
                    "name": "Noi Bai International Airport",
                    "role": ["outbound_arrival"],
                    "arrival": "07:00",
                    "departure": "09:30",
                    "note": "Flight VN123, Vietnam Airlines. Departs 07:00 SGN → arrives 09:00 HAN. ~30 min for luggage and customs."
                },
                {
                    "name": "Hotel X",
                    "role": ["luggage_drop"],
                    "arrival": "10:15",
                    "departure": "10:45",
                    "note": "Drop luggage at hotel before exploring."
                },
                {
                    "name": "Temple of Literature",
                    "role": ["attraction"],
                    "includes": [],
                    "arrival": "11:00",
                    "departure": "12:30",
                    "note": "Buy calligraphy art and handcrafted souvenirs."
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
                    "note": "Hotel check-in from 14:00 and afternoon rest."
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
                    "note": "Return to hotel for overnight stay."
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
- Each day starts with `start_day` (or `outbound_arrival` on day 1) and ends with `end_day` (or `return_departure` on last day)
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
    """Parse 'HH:MM' or 'HH:MM +1'/'-1' to minutes since midnight."""
    if not time_str:
        return 0
    clean = re.sub(r'\s*[+-]\d+\s*$', '', time_str.strip())
    parts = clean.split(":")
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


def _auto_correct_schedule(
    schedule: dict,
    schedule_constraints: dict | None = None,
) -> None:
    """Auto-correct common LLM mistakes IN-PLACE before validation.

    Current corrections:
    - If a non-first day starts with check_out (without start_day),
      prepend a start_day stop so the day structure is valid.
      The LLM frequently starts the last day with check_out because it
      thinks that's the logical first action, forgetting that every day
      must begin with start_day.
    """
    constraints = schedule_constraints or {}

    for day_data in schedule.get("days", []):
        day_idx = day_data.get("day", 1)
        stops = day_data.get("stops", [])
        if not stops or day_idx == 1:
            continue

        first_stop = stops[0]
        first_roles = first_stop.get("role", [])
        if isinstance(first_roles, str):
            first_roles = [first_roles]

        # Only fix if first stop has check_out but NOT start_day
        has_checkout = "check_out" in first_roles
        has_start_day = "start_day" in first_roles

        if has_checkout and not has_start_day:
            # Add start_day role to the existing check_out stop
            first_roles.insert(0, "start_day")
            first_stop["role"] = first_roles
            logger.info(
                f"   🔧 [AUTO-CORRECT] Day {day_idx}: added 'start_day' role "
                f"to check_out stop '{first_stop.get('name', '')}'"
            )


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
    last_day_idx = num_days if num_days > 0 else None

    # --- Track check_in across days (for rest validation) ---
    checked_in = False  # Becomes True once check_in appears in any day

    # --- Per-day checks ---
    for day_data in schedule.get("days", []):
        day_idx = day_data.get("day", 1)
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
                    
                # --- Check 13: No consecutive meals without activity in between ---
                prev_roles = _get_roles(prev_stop)
                if (roles & {"lunch", "dinner"}) and (prev_roles & {"lunch", "dinner"}):
                    violations.append({
                        "day": day_idx, "stop_name": name,
                        "issue": f"Cannot schedule a meal ({roles}) immediately after another meal ({prev_roles}). Add an activity (attraction/generic/rest) in between to represent the time spent, or merge them if they are the same meal.",
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

            # Lunch check removed to allow flexible skipping or late lunches.

            # Dinner required if schedule spans significantly past 19:30 (1170 min)
            if first_dep_min < 1170 and last_arr_min > 1170:
                if "dinner" not in all_roles_in_day:
                    violations.append({
                        "day": day_idx, "stop_name": "Dinner",
                        "issue": f"Day {day_idx} has continuous activity after 19:30 but NO dinner scheduled",
                    })

        # --- Check 9: Mandatory daily start/end structure ---
        if stops:
            first_roles = _get_roles(stops[0])
            last_roles = _get_roles(stops[-1])
            is_first_day = (day_idx == 1)
            is_last_day = (last_day_idx is not None and day_idx == last_day_idx)

            if is_first_day:
                if not (first_roles & {"outbound_arrival", "start_day"}):
                    violations.append({
                        "day": day_idx, "stop_name": stops[0].get("name", ""),
                        "issue": f"Day 1 must START with 'outbound_arrival' or 'start_day', got {sorted(first_roles)}",
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
# MODIFY MODE
# ============================================================================

def _apply_constraint_overrides(schedule_constraints: dict, overrides: dict) -> dict:
    """Apply user-provided constraint overrides to schedule_constraints.

    Overwrites the old times so that both the LLM prompt and code validation
    use the user's new values. Returns a modified copy.

    Supported override keys:
        outbound_departure_time: "HH:MM" → updates day_0_arrival with departure info
        outbound_arrival_time: "HH:MM" → updates day_0_arrival.arrival_time
        return_departure_time: "HH:MM" → updates last_day_deadline (recalc -2h)
        return_arrival_time: "HH:MM" → updates last_day_deadline with arrival info
        hotels: [{nights: [1,2,3], check_in_time, check_out_time}] → per-segment hotel overrides
    """
    import copy
    constraints = copy.deepcopy(schedule_constraints)

    # Override outbound departure time
    if "outbound_departure_time" in overrides:
        new_time = overrides["outbound_departure_time"]
        if "day_0_arrival" not in constraints:
            constraints["day_0_arrival"] = {}
        constraints["day_0_arrival"]["departure_time"] = new_time
        logger.info(f"   🔧 Override day_0_arrival.departure_time → {new_time}")

    # Override outbound arrival time
    if "outbound_arrival_time" in overrides:
        new_time = overrides["outbound_arrival_time"]
        if "day_0_arrival" not in constraints:
            constraints["day_0_arrival"] = {}
        constraints["day_0_arrival"]["arrival_time"] = new_time
        # Recalculate ready_time (+30min buffer for luggage/customs)
        try:
            parts = new_time.split(":")
            arr_min = int(parts[0]) * 60 + int(parts[1])
            ready_min = arr_min + 30
            constraints["day_0_arrival"]["ready_time"] = f"{ready_min // 60:02d}:{ready_min % 60:02d}"
        except (ValueError, IndexError):
            pass
        logger.info(f"   🔧 Override day_0_arrival.arrival_time → {new_time}")

    # Update note for day_0_arrival if any outbound override was applied
    if "outbound_departure_time" in overrides or "outbound_arrival_time" in overrides:
        dep = constraints.get("day_0_arrival", {}).get("departure_time", "?")
        arr = constraints.get("day_0_arrival", {}).get("arrival_time", "?")
        constraints["day_0_arrival"]["note"] = f"User override: flight {dep} → {arr}"

    # Override return departure time
    if "return_departure_time" in overrides:
        new_time = overrides["return_departure_time"]
        try:
            parts = new_time.split(":")
            dep_min = int(parts[0]) * 60 + int(parts[1])
            # Must arrive at airport 2h before flight
            deadline_min = max(480, dep_min - 120)
            deadline_time = f"{deadline_min // 60:02d}:{deadline_min % 60:02d}"
        except (ValueError, IndexError):
            deadline_time = new_time

        if "last_day_deadline" not in constraints:
            constraints["last_day_deadline"] = {}
        constraints["last_day_deadline"]["deadline_time"] = deadline_time
        constraints["last_day_deadline"]["flight_departure"] = new_time
        logger.info(f"   🔧 Override last_day_deadline → departure={new_time}, deadline={deadline_time}")

    # Override return arrival time
    if "return_arrival_time" in overrides:
        new_time = overrides["return_arrival_time"]
        if "last_day_deadline" not in constraints:
            constraints["last_day_deadline"] = {}
        constraints["last_day_deadline"]["arrival_time"] = new_time
        logger.info(f"   🔧 Override last_day_deadline.arrival_time → {new_time}")

    # Update note for last_day_deadline if any return override was applied
    if "return_departure_time" in overrides or "return_arrival_time" in overrides:
        dep = constraints.get("last_day_deadline", {}).get("flight_departure", "?")
        arr = constraints.get("last_day_deadline", {}).get("arrival_time", "?")
        dl = constraints.get("last_day_deadline", {}).get("deadline_time", "?")
        constraints["last_day_deadline"]["note"] = (
            f"User override: return flight at {dep} (arrives {arr}). "
            f"Must arrive at airport by {dl}."
        )

    # Override hotel check-in/check-out times (per-segment with nights)
    hotel_overrides = overrides.get("hotels", [])
    if hotel_overrides and constraints.get("hotels"):
        existing_hotels = constraints["hotels"]
        for override in hotel_overrides:
            override_nights = set(override.get("nights", []))
            ci_time = override.get("check_in_time")
            co_time = override.get("check_out_time")

            for hotel in existing_hotels:
                # Match by check_in_day (1-based, night number = check_in_day)
                hotel_night = hotel.get("check_in_day", -1)
                if hotel_night in override_nights or not override_nights:
                    if ci_time:
                        hotel["check_in_time"] = ci_time
                    if co_time:
                        hotel["check_out_time"] = co_time

            override_desc = f"nights={list(override_nights)}"
            if ci_time:
                override_desc += f", check_in={ci_time}"
            if co_time:
                override_desc += f", check_out={co_time}"
            logger.info(f"   🔧 Override hotel: {override_desc}")

    return constraints


ITINERARY_MODIFY_SYSTEM = """You are the Itinerary Scheduling Agent in MODIFY MODE.
You are modifying an EXISTING schedule that the user has ALREADY APPROVED.
Your job is to make ONLY the changes the user requested while keeping the rest intact.

## Your Task
1. Read the user's modification request carefully
2. Check the Day Mapping to understand which day the user is referring to
3. Check FEASIBILITY & COMPROMISE: Check if the user's EXACT requested change contradicts constraints (e.g., asking to visit place X in the morning, but X is closed in the morning).
   - If the user's exact request contradicts constraints, you MUST STILL GENERATE A VALID SCHEDULE. Do your best to find a compromise (e.g., moving it to the afternoon instead of morning).
   - Set the `fulfilled_user_request` field in your JSON output to `false`.
   - Write a detailed `modification_notes` string explaining WHY you couldn't fulfill their exact request and what compromise you made instead.
   - If the request WAS smoothly fulfilled without compromising their specific instructions, set `fulfilled_user_request: true`.
4. Modify the schedule, keeping unchanged parts intact.

## Suggesting New Attractions
If user asks to replace an attraction with something specific (e.g., "replace X with Museum of Ethnology"):
- Use the exact name they specified.
- You MUST use `resolve_first` mode to resolve this place.

If user asks to replace or add without naming a specific place (e.g., "replace with something else", "add something interesting"):
- Suggest a specific attraction from YOUR KNOWLEDGE that fits:
  - Same geographic area as the old attraction
  - Matches the user's interests from plan_context
  - Use the EXACT NAME as it appears on Google Maps
- You MUST use `resolve_first` mode to resolve this suggested place.
- Do NOT suggest places already in the schedule.

## DUAL OUTPUT MODE (IMPORTANT!)
When the user's request involves ANY new places (either they named it, or they asked for "something interesting" and you picked a specific name):
- Output ONLY the place names for resolution — do NOT generate a full schedule yet.
- Use this format:
{{
    "mode": "resolve_first",
    "places_to_resolve": ["Place Name 1", "Place Name 2"],
    "action_summary": "User wants to add Place Name 1 to afternoon of day 2 and replace X with Place Name 2 on day 3"
}}

When the user's request requires NO NEW PLACES (only removing, reordering, or minor time changes):
- Output the FULL modified schedule directly (normal mode).
- Use this format:
{{
    "mode": "direct_schedule",
    "days": [...],
    "dropped": [...],
    ...
}}

Examples of "resolve_first" triggers:
- "Thêm Bảo Tàng Dân Tộc Học vào ngày 2" → resolve_first: ["Bảo Tàng Dân Tộc Học"]
- "Thay Văn Miếu bằng Lotte Center" → resolve_first: ["Lotte Center"]
- "Thêm gì đó thú vị vào chiều ngày 2" → resolve_first: ["Suggested Place Name"]

Examples of "direct_schedule" (NO new places needed):
- "Xóa Văn Miếu khỏi ngày 2" → direct_schedule (removing only)
- "Dời ăn trưa lên 11:30" → direct_schedule (time change only)
- "Đổi thứ tự ngày 1 và ngày 2" → direct_schedule (reorder only)

## Constraint Override
If user explicitly provides new flight/hotel times (e.g., "my flight is at 15:00", "I'll check in at 13:00"):
- Use the user's times, OVERRIDE the constraints below
- Add a note to remind the user about implications:
  - Flight: "Remember to arrive at the airport at least 2 hours early"
  - Hotel: "Make sure this is within the hotel's allowed check-in/check-out time"

## Modification Rules
- ONLY change what the user requested or what's DIRECTLY AFFECTED by the change.
- Unaffected days MUST be kept exactly as they are — the user already approved them.
- FOR AFFECTED DAYS (e.g. flight/hotel time changes): You MUST holistically re-pace the day to ensure a natural flow. Do not just shift the flight/hotel time and leave awkward gaps or rushed overlaps.
  - Preserve core activities: Your primary goal is to KEEP existing user-approved activities. ONLY add or drop activities to resolve time gaps or conflicts.
  - Adapt to expanded time: If there is a large gap, extend durations of current activities, shift meals, handle luggage logistics (e.g. early drop-off), or introduce minor filler activities (e.g., "Explore local neighborhood", "Cafe rest").
  - Adapt to compressed time: If time is cut short, shorten durations or drop non-essential activities to keep the schedule feasible without rushing.
  - Logical flow: Always ensure the sequence makes physical sense (e.g. do not go sightseeing with luggage immediately after landing if the hotel is far; drop luggage first).
- If adding an attraction: fit it into the requested slot, adjust neighboring stops' times.
- If swapping attractions: replace the old with the new, adjust times for duration differences.
- Respect all constraints: opening hours, hotel check-in/out, meals, etc.
- Each attraction stop MUST have an "includes" field (list, or empty [])
- Write all notes in {language}

## Response Format

For direct_schedule mode, return ALL days (even unchanged ones) in this format:
{{
    "mode": "direct_schedule",
    "days": [
        {{
            "day": 1,
            "title": "...",
            "stops": [
                {{"name": "...", "role": ["..."], "arrival": "HH:MM", "departure": "HH:MM", "includes": [], "note": "..."}}
            ]
        }}
    ],
    "dropped": ["..."],
    "more_attractions": [],
    "fulfilled_user_request": true,
    "modification_notes": "I moved X to the morning exactly as you asked."
}}

### CRITICAL — Exact Name Rule
You MUST use the EXACT attraction and hotel names as provided in the input data. Do NOT modify, abbreviate, translate, add parentheses, or append alternative names. Copy the name character-for-character. If you want to add context (e.g., Vietnamese name, sub-attractions), put it in the `note` field instead.

## Critical Rules
- All times in HH:MM (24-hour clock)
- `role` is ALWAYS a list: ["attraction"], ["lunch"], ["check_in", "rest"]
- For `start_day`: arrival = departure (just depart)
- For `end_day`: departure = "" (just arrive)
- NEVER schedule during "Closed" hours
- Meals: lunch 11:00-13:00, dinner 18:00-20:00 — keep existing meals unless directly affected
- Output ONLY raw JSON. No text before or after.
"""

_MODIFY_WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


async def _build_new_attractions_info(
    attraction_data: dict,
    plan_context: dict,
) -> list[dict]:
    """Build attractions_info (with per-day opening hours) for newly found attractions."""
    from datetime import datetime, timedelta
    from src.tools.dotnet_tools import get_place_from_db

    new_info = []
    start_date_str = plan_context.get("start_date", "")
    num_days = plan_context.get("num_days", 1)

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else datetime.now()
    except ValueError:
        start_date = datetime.now()

    day_weekday_names = []
    for d in range(num_days):
        day_date = start_date + timedelta(days=d)
        day_weekday_names.append(_MODIFY_WEEKDAY_NAMES[day_date.weekday()])

    for segment in attraction_data.get("segments", []):
        for attr in segment.get("attractions", []):
            place_id = attr.get("placeId")
            if not place_id:
                continue

            # Fetch place data from DB for opening hours
            try:
                db_result = await get_place_from_db.ainvoke({"place_id": place_id})
                if not (isinstance(db_result, dict) and db_result.get("success")):
                    continue
                place_data = db_result.get("data", {})
            except Exception as e:
                logger.warning(f"Failed to fetch place data for {attr.get('name')}: {e}")
                continue

            open_hours = place_data.get("openHours", {})
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

            new_info.append({
                "name": place_data.get("title", attr.get("name", "")),
                "opening_hours": hours_by_day,
                "must_visit": attr.get("must_visit", False),
                "segment_name": segment.get("segment_name", ""),
                "includes": attr.get("includes", []),
                "notes": attr.get("notes", ""),
            })

    return new_info


def _build_modify_prompt(
    existing_schedule: dict,
    attractions_info: list[dict],
    distance_pairs: list[dict],
    schedule_constraints: dict,
    user_request: str,
    plan_context: dict = None,
    weather_data: dict = None,
) -> str:
    """Build the human message for the LLM modify scheduler."""
    sections = []

    # ── Day Mapping ── (fix day indexing confusion)
    if plan_context:
        start_date_str = plan_context.get("start_date", "")
        num_days = plan_context.get("num_days", 0)
        language = plan_context.get("language", "en")

        if start_date_str and num_days:
            from datetime import datetime, timedelta
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            except ValueError:
                start_date = None

            if start_date:
                vi_weekdays = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm",
                               "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
                en_weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday",
                               "Friday", "Saturday", "Sunday"]
                weekdays = vi_weekdays if language == "vi" else en_weekdays

                sections.append("## Day Mapping (reference for user date requests)")
                sections.append("Days use 1-based index: Day 1 = first day, Day 2 = second day, etc.")

                for i in range(num_days):
                    day_date = start_date + timedelta(days=i)
                    wday_name = weekdays[day_date.weekday()]
                    date_str = day_date.strftime("%d/%m/%Y")
                    sections.append(f"- day {i+1} → {wday_name}, {date_str}")

                if language == "vi":
                    sections.append(
                        'LƯU Ý:\n'
                        '- "ngày 2" hoặc "ngày thứ 2" = `day`: 2 trong JSON.\n'
                        '- "ngày 16/4" → tra bảng trên để biết day index tương ứng.\n'
                        '- Thứ trong tuần: "Thứ Hai" = Monday. Dùng bảng trên để tra.'
                    )
                else:
                    sections.append(
                        'NOTE:\n'
                        '- "day 2" or "the 2nd day" = `day`: 2 in JSON.\n'
                        '- Map weekday names or dates to day indices using the table above.'
                    )
                sections.append("")

    # Existing schedule
    existing_days = existing_schedule.get("days", [])
    sections.append("## Your Existing Schedule (user has approved this)\n")
    sections.append(json.dumps({"days": existing_days}, indent=2, ensure_ascii=False))
    sections.append("")

    # Attractions opening hours
    sections.append("## Attractions Opening Hours\n")
    for attr in attractions_info:
        title = f"### {attr['name']}"
        if attr.get("must_visit"):
            title += " (⭐ MUST-VISIT: You MUST include this in the schedule)"
        sections.append(title)
        if attr.get("includes"):
            inc_names = [i.get("name", str(i)) if isinstance(i, dict) else str(i) for i in attr["includes"]]
            sections.append(f"- Includes (sub-attractions within/adjacent): {', '.join(inc_names)}")
        sections.append("- Opening hours:")
        for day_key, hours in attr["opening_hours"].items():
            sections.append(f"  - {day_key}: {hours}")
        sections.append("")

    # Distance matrix (if available)
    if distance_pairs:
        sections.append("## Travel Times (raw minutes)")
        sections.append("| From | To | Travel Time (min) |")
        sections.append("|------|----|-------------------|")
        for pair in distance_pairs:
            sections.append(f"| {pair['from']} | {pair['to']} | {pair['raw_minutes']} |")
        sections.append("")

    # Schedule constraints
    if schedule_constraints:
        sections.append("## Schedule Constraints")
        sections.append(json.dumps(schedule_constraints, indent=2, ensure_ascii=False))
        sections.append("")

    # Weather context (reuse from previous run)
    if weather_data and weather_data.get("daily"):
        sections.append("## Weather Forecast (for context)")
        for day_w in weather_data["daily"]:
            rain = f", rain chance: {day_w.get('rain_chance_pct', '?')}%" if 'rain_chance_pct' in day_w else ""
            sections.append(
                f"- Day {day_w['day']} ({day_w.get('date', '?')}): "
                f"{day_w.get('condition', '?')}, {day_w.get('temp_min', '?')}\u2013{day_w.get('temp_max', '?')}\u00b0C{rain}"
            )
        sections.append("")

    # User's modification request
    sections.append("## User's Active Modification Goal")
    sections.append(f"Latest User Message: \"{user_request}\"")
    sections.append("")
    sections.append("Modify the schedule to satisfy the User's Active Goal. Output ONLY the JSON.")

    return "\n".join(sections)


async def _itinerary_modify_mode(state: GraphState) -> dict[str, Any]:
    """Handle itinerary modification in MODIFY mode.

    2-pass process:
    Pass 1: LLM modifies the schedule (may suggest new attractions with _is_new=true,
            or handle generic requests with guessed times)
    Post-resolve: resolve placeIds + fetch opening hours + compute distances for _is_new places
    Pass 2 (if _is_new resolved): re-prompt LLM with newly resolved real data
            so it can re-schedule accurately with real opening hours + distances.

    Uses cached pipeline data from previous run instead of re-running the full pipeline.
    Supports feasibility check and guided re-schedule.
    """
    logger.info("=" * 60)
    logger.info("\U0001f4c5 [ITINERARY_AGENT_MODIFY] Entering modify mode")

    current_plan = state.get("current_plan", {})
    existing_itinerary = current_plan.get("itinerary", {})
    plan_context = current_plan.get("plan_context", {})

    # Check if there's an existing itinerary to modify
    if not existing_itinerary.get("days"):
        logger.error("\U0001f4c5 [ITINERARY_AGENT_MODIFY] No existing itinerary to modify")
        return {
            "agent_outputs": {"itinerary_agent": {
                "error": True,
                "message": "No existing itinerary to modify",
                "days": [], "dropped": [], "method": "llm_modify",
            }},

        }

    # Get user modification request
    # If triggered by select_and_apply, use the auto-generated message
    constraint_overrides = state.get("constraint_overrides", {})
    if constraint_overrides and constraint_overrides.get("auto_user_message"):
        user_message = constraint_overrides["auto_user_message"]
        logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Selection-triggered rerange: {user_message[:100]}")
    else:
        intent_output = state.get("intent_output") or {}
        if intent_output.get("user_request_rewrite"):
            user_message = intent_output["user_request_rewrite"]
            logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Using explicit Intent user_request_rewrite: {user_message[:100]}")
        else:
            user_message = state.get("user_message", "")
            logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Using raw user request: {user_message[:100]}")

    # Get cached pipeline data from previous itinerary run
    cached_pipeline = existing_itinerary.get("_cached_pipeline", {})
    attractions_info = list(cached_pipeline.get("attractions_info", []))
    distance_pairs = cached_pipeline.get("distance_pairs", [])
    schedule_constraints = cached_pipeline.get("schedule_constraints", {})

    # Apply constraint overrides from Intent Agent or select_and_apply node
    constraint_overrides = state.get("constraint_overrides", {})
    if constraint_overrides:
        logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Applying constraint overrides: {constraint_overrides}")
        schedule_constraints = _apply_constraint_overrides(schedule_constraints, constraint_overrides)

    # Get weather data (reuse from previous run if available)
    weather_data = state.get("agent_outputs", {}).get("weather", {})

    # Build modify prompt
    language = plan_context.get("language", "en")
    system_content = ITINERARY_MODIFY_SYSTEM.replace("{language}", language)
    human_content = _build_modify_prompt(
        existing_schedule=existing_itinerary,
        attractions_info=attractions_info,
        distance_pairs=distance_pairs,
        schedule_constraints=schedule_constraints,
        user_request=user_message,
        plan_context=plan_context,
        weather_data=weather_data,
    )

    messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=human_content),
    ]

    # ── Step 1: LLM call — dual output mode ──
    max_retries = 2
    best_result = None
    itinerary_result = {}
    violations = []
    encountered_violations = []
    resolve_first_places = None  # Track if Pass 1 returned resolve_first mode

    try:
        logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Pass 1: Initial LLM call")
        result = await llm_itinerary.ainvoke(messages)
        parsed = _extract_json(result.content)

        output_mode = parsed.get("mode", "direct_schedule")

        if output_mode == "resolve_first":
            # ── resolve_first mode: LLM returned place names only ──
            resolve_first_places = parsed.get("places_to_resolve", [])
            action_summary = parsed.get("action_summary", "")
            logger.info(f"📅 [ITINERARY_AGENT_MODIFY] resolve_first mode: {resolve_first_places}")
            logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Action: {action_summary}")
            # Will be handled in Step 2 below
        else:
            # ── direct_schedule mode: normal full schedule ──
            logger.info(f"📅 [ITINERARY_AGENT_MODIFY] direct_schedule mode")
            _auto_correct_schedule(parsed, schedule_constraints)
            violations = _validate_schedule(
                parsed, attractions_info, schedule_constraints, distance_pairs
            )

            if not violations:
                logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Valid on attempt 1")
                best_result = parsed
            else:
                logger.warning(f"📅 [ITINERARY_AGENT_MODIFY] {len(violations)} violations on attempt 1")
                for v in violations:
                    logger.warning(f"      Day {v['day']}: {v['stop_name']} — {v['issue']}")
                best_result = parsed

                for v in violations:
                    if any(kw in v["issue"] for kw in ["Closed", "opens at", "closes at"]):
                        note = f"{v['stop_name']}: {v['issue']}"
                        if note not in encountered_violations:
                            encountered_violations.append(note)

                # Retry loop (only for direct_schedule mode)
                for attempt in range(1, max_retries + 1):
                    violation_text = "\n".join(
                        f"- Day {v['day']}: {v['stop_name']} — {v['issue']}" for v in violations
                    )
                    messages.append(AIMessage(content=result.content))
                    retry_msg = f"Your modified schedule has {len(violations)} violations:\n{violation_text}\n\n"
                    retry_msg += (
                        "CRITICAL INSTRUCTION: If these violations mean you CANNOT fulfill the user's specific request "
                        "(e.g., they asked to visit a place at a time when it is closed, or in an order that violates opening hours), "
                        "YOU MUST FIX THE SCHEDULE TO BE VALID (e.g., move it to a time when it is open).\n"
                        "BUT you MUST set `\"fulfilled_user_request\": false` at the root of your JSON, and explicitly explain "
                        "your compromise in `\"modification_notes\"`.\n\n"
                        "If the violations are just minor scheduling mistakes (like overlapping times) that CAN be fixed while still "
                        "respecting the user's wishes, fix them and return the COMPLETE corrected JSON schedule with `\"fulfilled_user_request\": true`."
                    )
                    messages.append(HumanMessage(content=retry_msg))

                    logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Retry attempt {attempt + 1}/{max_retries + 1}")
                    result = await llm_itinerary.ainvoke(messages)
                    parsed = _extract_json(result.content)
                    _auto_correct_schedule(parsed, schedule_constraints)
                    violations = _validate_schedule(
                        parsed, attractions_info, schedule_constraints, distance_pairs
                    )

                    if not violations:
                        logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Valid on attempt {attempt + 1}")
                        best_result = parsed
                        break

                    logger.warning(f"📅 [ITINERARY_AGENT_MODIFY] {len(violations)} violations on attempt {attempt + 1}")
                    best_result = parsed
                    for v in violations:
                        if any(kw in v["issue"] for kw in ["Closed", "opens at", "closes at"]):
                            note = f"{v['stop_name']}: {v['issue']}"
                            if note not in encountered_violations:
                                encountered_violations.append(note)

            # Post-retry: build itinerary_result
            if not itinerary_result:
                itinerary_result = best_result or {"days": [], "dropped": []}
                itinerary_result["method"] = "llm_modify"
                itinerary_result["error"] = False
                itinerary_result["fulfilled_user_request"] = best_result.get("fulfilled_user_request", True)

                ai_notes = best_result.get("modification_notes", "")
                if encountered_violations and not itinerary_result["fulfilled_user_request"]:
                    combo_notes = f"{ai_notes}\n\nConstraints encountered during adjustments:\n" + "\n".join(f"- {v}" for v in encountered_violations)
                    itinerary_result["modification_notes"] = combo_notes.strip()
                    logger.info(f"📅 [MODIFY] Request compromise notes:\n{itinerary_result['modification_notes']}")
                else:
                    itinerary_result["modification_notes"] = ai_notes

                if violations:
                    itinerary_result["warnings"] = violations

    except Exception as e:
        logger.error(f"📅 [ITINERARY_AGENT_MODIFY] Error: {e}", exc_info=True)
        itinerary_result = {
            "error": True,
            "message": str(e),
            "days": existing_itinerary.get("days", []),
            "dropped": existing_itinerary.get("dropped", []),
            "method": "llm_modify",
        }

    # ── Step 2: Resolve + Pass 2 ──
    if resolve_first_places:
        # ── resolve_first path: resolve named places → Pass 2 full schedule ──
        logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Resolving {len(resolve_first_places)} place(s): {resolve_first_places}")
        from src.services.place_resolution_llm import resolve_place_names_batch
        from datetime import datetime, timedelta
        from src.services.itinerary_builder import build_symmetric_distance_pairs
        from src.tools.itinerary_tools import _build_distance_matrix
        from src.tools.maps_tools import LOCAL_TRANSPORT_MAP

        destination = plan_context.get("destination", "")

        resolved_items = await resolve_place_names_batch(
            names=resolve_first_places,
            destination=destination,
            location_bias=destination
        )

        if resolved_items:
            logger.info(f"📅 [MODIFY_RESOLVE] Resolved {len(resolved_items)}/{len(resolve_first_places)} place(s) using LLM batch")

            # Build attractions_info for resolved places
            start_date_str = plan_context.get("start_date", "")
            num_days = plan_context.get("num_days", 1)
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d") if start_date_str else datetime.now()
            day_weekday_names = [_MODIFY_WEEKDAY_NAMES[(start_date + timedelta(days=d)).weekday()] for d in range(num_days)]

            new_attractions_info = []
            new_locations = []

            for item in resolved_items:
                db_data = item.get("db_data", {})
                attr_name = item.get("title", item["original_name"])
                open_hours = db_data.get("openHours", {})

                hours_by_day = {}
                for day_idx in range(num_days):
                    day_name = day_weekday_names[day_idx]
                    day_label = f"day_{day_idx + 1} ({day_name[:3].capitalize()})"
                    if not open_hours:
                        hours_by_day[day_label] = "08:00-22:00 (assumed)"
                    else:
                        hours_list = open_hours.get(day_name, [])
                        if not hours_list:
                            all_empty = all(len(v) == 0 for v in open_hours.values())
                            hours_by_day[day_label] = "08:00-22:00 (assumed)" if all_empty else "Closed"
                        elif len(hours_list) == 1:
                            single = hours_list[0].strip().lower()
                            if single == "closed":
                                hours_by_day[day_label] = "Closed"
                            elif "open 24" in single or "24 hours" in single:
                                hours_by_day[day_label] = "Open 24 hours"
                            else:
                                hours_by_day[day_label] = ", ".join(hours_list)
                        else:
                            hours_by_day[day_label] = ", ".join(hours_list)

                new_attractions_info.append({
                    "name": attr_name,
                    "opening_hours": hours_by_day,
                    "must_visit": False, "segment_name": "", "includes": [],
                    "notes": "", "estimated_entrance_fee": {"total": 0, "note": ""},
                })

                location = db_data.get("location") or {}
                coords = location.get("coordinates", [])
                if len(coords) >= 2:
                    new_locations.append({"name": attr_name, "lat": coords[1], "lng": coords[0], "type": "attraction"})

            # Compute distances
            new_distance_pairs = []
            if new_locations:
                existing_resolved = existing_itinerary.get("resolved_places", {})
                existing_locations = []
                for group_name in ["airports", "hotels", "attractions"]:
                    for item in existing_resolved.get(group_name, []):
                        res = item.get("resolved")
                        if not res: continue
                        title = res.get("title", "")
                        loc = res.get("location") or {}
                        coords = loc.get("coordinates", [])
                        if title and len(coords) >= 2:
                            existing_locations.append({"name": title, "lat": coords[1], "lng": coords[0], "type": group_name.rstrip("s")})

                all_locs = existing_locations + new_locations
                if len(all_locs) >= 2:
                    try:
                        transport = plan_context.get("local_transportation", "car")
                        travel_mode = LOCAL_TRANSPORT_MAP.get(transport, "DRIVE")
                        dm = await _build_distance_matrix(all_locs, travel_mode=travel_mode)
                        if dm:
                            all_pairs = build_symmetric_distance_pairs(all_locs, dm)
                            new_loc_names = {loc["name"] for loc in new_locations}
                            new_distance_pairs = [p for p in all_pairs if p.get("from") in new_loc_names or p.get("to") in new_loc_names]
                            logger.info(f"📅 [MODIFY_RESOLVE] Computed {len(new_distance_pairs)} distance pairs")
                    except Exception as e:
                        logger.warning(f"📅 [MODIFY_RESOLVE] Distance matrix failed: {e}")

            # Pass 2: Re-prompt with enriched data for FULL schedule
            enriched_attractions = list(attractions_info) + new_attractions_info
            enriched_distances = list(distance_pairs) + new_distance_pairs

            pass2_human = _build_modify_prompt(
                existing_schedule=existing_itinerary,
                attractions_info=enriched_attractions,
                distance_pairs=enriched_distances,
                schedule_constraints=schedule_constraints,
                user_request=user_message,
                plan_context=plan_context,
                weather_data=weather_data,
            )

            # Force direct_schedule in Pass 2 prompt
            pass2_system = system_content + "\n\nIMPORTANT: You MUST output a direct_schedule with the full schedule. Do NOT output resolve_first again."

            pass2_messages = [
                SystemMessage(content=pass2_system),
                HumanMessage(content=pass2_human),
            ]

            try:
                logger.info("📅 [ITINERARY_AGENT_MODIFY] Pass 2: Generating full schedule with resolved data")
                pass2_raw = await llm_itinerary.ainvoke(pass2_messages)
                pass2_parsed = _extract_json(pass2_raw.content)
                _auto_correct_schedule(pass2_parsed, schedule_constraints)

                violations = _validate_schedule(pass2_parsed, enriched_attractions, schedule_constraints, enriched_distances)
                itinerary_result = pass2_parsed
                itinerary_result["method"] = "llm_modify"
                itinerary_result["error"] = False
                itinerary_result["fulfilled_user_request"] = pass2_parsed.get("fulfilled_user_request", True)
                itinerary_result["modification_notes"] = pass2_parsed.get("modification_notes", "")
                if violations:
                    itinerary_result["warnings"] = violations
                attractions_info = enriched_attractions
                distance_pairs = enriched_distances
                logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Pass 2 complete ({len(violations)} violations)")
            except Exception as e:
                logger.error(f"📅 [ITINERARY_AGENT_MODIFY] Pass 2 failed: {e}")
                itinerary_result = {
                    "error": True, "message": f"Pass 2 failed: {e}",
                    "days": existing_itinerary.get("days", []),
                    "dropped": existing_itinerary.get("dropped", []),
                    "method": "llm_modify",
                }
        else:
            logger.warning("📅 [MODIFY_RESOLVE] None of the places could be resolved — falling back to direct schedule")
            # Force direct_schedule mode: replace system prompt and add explicit instruction
            fallback_system = system_content + "\n\nIMPORTANT: You MUST output a direct_schedule with the full schedule. Do NOT output resolve_first again. The places could not be found — use your best knowledge to add suitable alternatives."
            fallback_messages = [
                SystemMessage(content=fallback_system),
                HumanMessage(content=messages[-1].content if messages else "Please provide the modified schedule using direct_schedule mode."),
            ]
            try:
                fallback_raw = await llm_itinerary.ainvoke(fallback_messages)
                fallback_parsed = _extract_json(fallback_raw.content)
                _auto_correct_schedule(fallback_parsed, schedule_constraints)
                violations = _validate_schedule(fallback_parsed, attractions_info, schedule_constraints, distance_pairs)
                itinerary_result = fallback_parsed
                itinerary_result["method"] = "llm_modify"
                itinerary_result["error"] = False
                if violations:
                    itinerary_result["warnings"] = violations
            except Exception as e:
                logger.error(f"📅 [ITINERARY_AGENT_MODIFY] Fallback failed: {e}")
                itinerary_result = {
                    "error": True, "message": str(e),
                    "days": existing_itinerary.get("days", []),
                    "dropped": [], "method": "llm_modify",
                }

    # Preserve metadata from existing itinerary
    itinerary_result["plan_context"] = {
        "start_date": plan_context.get("start_date", ""),
        "end_date": plan_context.get("end_date", ""),
        "num_days": plan_context.get("num_days", 0),
        "destination": plan_context.get("destination", ""),
    }
    if "resolved_places" not in itinerary_result:
        itinerary_result["resolved_places"] = existing_itinerary.get("resolved_places", {})
    itinerary_result["_cached_pipeline"] = {
        "attractions_info": attractions_info,
        "distance_pairs": distance_pairs,
        "schedule_constraints": schedule_constraints,
    }

    num_days = len(itinerary_result.get("days", []))
    is_feasibility = itinerary_result.get("feasibility_issue", False)
    status = "feasibility issue" if is_feasibility else f"{num_days} days"
    logger.info(f"📅 [ITINERARY_AGENT_MODIFY] Completed: {status}")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"itinerary_agent": itinerary_result},

    }


# ============================================================================
# AGENT NODE
# ============================================================================

async def itinerary_agent_node(state: GraphState) -> dict[str, Any]:
    """Itinerary Agent — Uses LLM to schedule attractions.

    Flow:
        1. Pipeline: extract → resolve → distance matrix → opening hours → constraints
        2. Prompt LLM with all data
        3. Validate schedule against opening hours
        4. Re-prompt if violations (max 2 retries)
        5. Return schedule
    """
    logger.info("=" * 60)
    logger.info("\U0001f4c5 [ITINERARY_AGENT] Node entered")

    # Check for modify mode (including selection-triggered rerange)
    intent = (state.get("intent_output") or {}).get("intent", "")
    if intent in ("modify_itinerary", "select_hotel", "select_flight"):
        return await _itinerary_modify_mode(state)

    agent_outputs = state.get("agent_outputs", {})
    plan = state.get("macro_plan", {})
    current_plan = state.get("current_plan", {})
    plan_context = current_plan.get("plan_context", {})
    mobility_plan = plan.get("mobility_plan", {})

    itinerary_result = {}

    try:
        # Phase 1: Build scheduling input
        logger.info("📅 [ITINERARY_AGENT] Phase 1: Building scheduling input...")
        pipeline_data = await run_itinerary_pipeline(agent_outputs, plan, plan_context, useRouteMatrix)

        if pipeline_data.get("error"):
            itinerary_result = {
                "error": True,
                "message": pipeline_data.get("message", "Pipeline failed"),
                "days": [], "dropped": [], "method": "llm",
            }
        else:
            # Apply constraint overrides if user provided flight/hotel times
            constraint_overrides = state.get("constraint_overrides", {})
            if constraint_overrides:
                logger.info(f"📅 [ITINERARY_AGENT] Applying constraint overrides: {constraint_overrides}")
                pipeline_data["schedule_constraints"] = _apply_constraint_overrides(
                    pipeline_data["schedule_constraints"], constraint_overrides
                )

            # Phase 2: LLM scheduling
            logger.info("📅 [ITINERARY_AGENT] Phase 2: LLM scheduling...")
            weather_data = agent_outputs.get("weather", {})
            human_content = _build_scheduling_prompt(pipeline_data, plan_context, mobility_plan, weather_data)

            # Inject language into system prompt for note generation
            language = plan_context.get("language", "en")
            system_content = ITINERARY_SCHEDULER_SYSTEM.replace("{language}", language)

            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=human_content),
            ]

            max_retries = 3
            best_schedule = None
            violations = []

            for attempt in range(max_retries + 1):
                logger.info(f"   Attempt {attempt + 1}/{max_retries + 1}: Invoking LLM...")
                result = await llm_itinerary.ainvoke(messages)
                schedule = _extract_json(result.content)


                _auto_correct_schedule(schedule, pipeline_data["schedule_constraints"])
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
            itinerary_result["_cached_pipeline"] = {
                "attractions_info": pipeline_data.get("attractions_info", []),
                "distance_pairs": pipeline_data.get("distance_pairs", []),
                "schedule_constraints": pipeline_data.get("schedule_constraints", {}),
            }

    except Exception as e:
        logger.error(f"   ❌ Itinerary Agent error: {e}", exc_info=True)
        itinerary_result = {"error": True, "message": str(e), "days": [], "dropped": [], "method": "llm"}

    num_days = len(itinerary_result.get("days", []))
    dropped = len(itinerary_result.get("dropped", []))

    logger.info(f"📅 [ITINERARY_AGENT] Completed: {num_days} days, {dropped} dropped")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"itinerary_agent": itinerary_result},

    }


# ============================================================================
# PROMPT BUILDER
# ============================================================================

def _build_scheduling_prompt(pipeline_data: dict, plan_context: dict, mobility_plan: dict = None, weather_data: dict | None = None) -> str:
    """Build the human message for the LLM scheduler."""

    attractions_info = pipeline_data["attractions_info"]
    distance_pairs = pipeline_data["distance_pairs"]
    constraints = pipeline_data["schedule_constraints"]
    mobility_plan = mobility_plan or {}

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

    # Day 1 arrival
    arrival = constraints.get("day_0_arrival")
    if arrival:
        sections.append(f"\n### Day 1 Arrival")
        sections.append(f"- Location: {arrival.get('location', '?')}")
        if arrival.get("departure_time"):
            sections.append(f"- Flight departure from origin: {arrival['departure_time']}")
        if arrival.get("start_time"):
            sections.append(f"- Route Start Time: {arrival['start_time']}")
        sections.append(f"- Landing/Arrival at destination: {arrival.get('arrival_time', '?')}")
        if arrival.get("flight_number"):
            sections.append(f"- Flight: {arrival.get('flight_number', '')} ({arrival.get('airline', '')})")
            sections.append(f"- From: {arrival.get('departure_airport', '')}")
        if arrival.get("ready_time"):
            sections.append(f"- Ready to explore (after luggage/customs): {arrival['ready_time']}")
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
