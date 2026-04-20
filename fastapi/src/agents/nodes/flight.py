import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.tools.dotnet_tools import search_airports, search_flights
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from src.config import settings
from src.services.place_resolver import resolve_single_place

logger = logging.getLogger(__name__)

llm_flight = (
    ChatOpenAI(
        model=settings.MODEL_NAME,
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model=settings.MODEL_NAME,
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_FLIGHT or settings.GOOGLE_GEMINI_API_KEY,
        temperature=0.3,
        streaming=False,
    )
)

FLIGHT_AGENT_SYSTEM = """You are the Flight Agent for a travel planning system.

You find flights using search_airports and search_flights tools.

## Input
You receive:
1. **plan_context**: Shared trip info (departure city, destination, dates, passengers, budget, currency)
2. **mobility_plan**: Trip logistics (if available)
3. **task**: Flight-specific requirements — type (one_way/round_trip), directions, preferred time windows (outbound_times/return_times), infants_in_seat/infants_on_lap, travel class, any user notes

## Determine Search Flow

Read `type` and `directions` from the task:
- **type**: "one_way" (default) or "round_trip"
- **directions**: "both" (default), "outbound_only", or "return_only"

| type       | directions     | Flow                          |
|-----------|----------------|-------------------------------|
| one_way   | both           | ONE-WAY DOUBLE SEARCH         |
| one_way   | outbound_only  | ONE-WAY OUTBOUND ONLY         |
| one_way   | return_only    | ONE-WAY RETURN ONLY           |
| round_trip| both           | ROUND-TRIP FLOW               |

## Process
1. Read plan_context and task carefully
2. Determine airport IATA codes from plan_context.departure and plan_context.destination:
   - Use your knowledge of common airports (e.g., "Ho Chi Minh City" → SGN, "Hanoi" → HAN)
   - If uncertain, call search_airports to find the nearest airports
3. Map task preferences and plan_context to search_flights parameters:
  - travel_class: "economy"→1, "premium_economy"→2, "business"→3, "first"→4
  - For round_trip: outbound_date = plan_context.start_date, return_date = plan_context.end_date
  - For one_way: outbound_date = plan_context.start_date (outbound) or end_date (return), do NOT pass return_date
  - max_price: pass if specified in task
  - **Convert outbound_times and return_times** from task to SerpApi format (see below)

## Converting Time Preferences to SerpApi Format

The task provides:
- `outbound_times` as desired ARRIVAL time at destination (e.g., "arrive 8:00 AM - 10:00 AM at destination")
- `return_times` as desired DEPARTURE time from destination (e.g., "depart 3:00 PM - 7:00 PM from destination")

You MUST convert these to SerpApi format before calling search_flights.

### SerpApi format rules:
- Two numbers "start,end": filters DEPARTURE time → range [start:00, (end+1):00)
- Four numbers "dep_start,dep_end,arr_start,arr_end": filters BOTH departure AND arrival
- Use "0,23" for unrestricted departure, "0,23,X,Y" for unrestricted departure + filtered arrival

### Conversion formula (IMPORTANT):
Given desired time range X:00 to Y:00 → SerpApi numbers = {X_24h},{Y_24h - 1}
(Because SerpApi range is [number:00, (number+1):00) — so "7" covers 7:00-7:59, displayed as ending at 8:00)

### 1. outbound_times (ARRIVAL-focused) → use 4-number format:
Extract arrival hours from "arrive X - Y at destination", convert to 24h, then:
SerpApi outbound_times = "0,23,{arrival_start_24h},{arrival_end_24h - 1}"
(unrestricted departure + filtered arrival)

| Orchestrator outbound_times              | SerpApi outbound_times |
|------------------------------------------|----------------------|
| "arrive 8:00 AM - 10:00 AM at destination" | "0,23,8,9"          |
| "arrive 9:00 AM - 12:00 PM at destination" | "0,23,9,11"         |
| "arrive 6:00 AM - 9:00 AM at destination"  | "0,23,6,8"          |

### 2. return_times (DEPARTURE-focused) → use 2-number format:
Extract departure hours from "depart X - Y from destination", convert to 24h, then:
SerpApi return_times = "{departure_start_24h},{departure_end_24h - 1}"

| Orchestrator return_times                  | SerpApi return_times |
|--------------------------------------------|---------------------|
| "depart 3:00 PM - 7:00 PM from destination" | "15,18"             |
| "depart 8:00 PM - 10:00 PM from destination"| "20,21"             |
| "depart 12:00 PM - 5:00 PM from destination"| "12,16"             |

### How to apply per search type:
- **ONE-WAY DOUBLE outbound leg**: Pass converted outbound_times (4-number arrival filter) as `outbound_times`
- **ONE-WAY DOUBLE return leg** (swapped airports): Pass converted return_times (2-number departure filter) as `outbound_times` parameter
- **ONE-WAY OUTBOUND ONLY**: Pass converted outbound_times as `outbound_times`
- **ONE-WAY RETURN ONLY** (swapped airports): Pass converted return_times as `outbound_times` parameter
- **ROUND-TRIP first search** (no departure_token): Pass both `outbound_times` and `return_times`
- **ROUND-TRIP second search** (with departure_token): Do NOT pass any time filters
- If outbound_times or return_times are null/not provided, do NOT pass them (unrestricted)

## No-Results Fallback — CRITICAL

After EVERY search_flights call, check results. If BOTH best_flights and other_flights are empty/null/missing:

**Retry 1 — Widen time window ±3 hours:**
  - Expand relevant start earlier and end later by 3h, clamp to [0, 23]
  - For 4-number format (arrival filter): widen arrival range. E.g., "0,23,8,9" → "0,23,5,12"
  - For 2-number format (departure filter): widen departure range. E.g., "15,18" → "12,21"
  - Retry search_flights with the widened time filter

**Retry 2 — Remove time filter entirely:**
  - If still no results, retry WITHOUT outbound_times/return_times at all

**Give up:** If still no results, set flights_found=false and explain in your note.
  - Mention in recommend_note that the time window was widened or removed during search.

## Search Flows

### ONE-WAY OUTBOUND ONLY (type="one_way", directions="outbound_only"):
4. Call search_flights (flight_type=2, outbound_date=start_date) with converted outbound_times
5. Apply No-Results Fallback if needed
6. Analyze all flights, return the most suitable ONE
7. Return JSON with recommend_outbound_flight only (return fields = null)

### ONE-WAY RETURN ONLY (type="one_way", directions="return_only"):
4. Call search_flights (flight_type=2, outbound_date=end_date, departure_id/arrival_id SWAPPED) with converted return_times as outbound_times
5. Apply No-Results Fallback if needed
6. Analyze all flights, return the most suitable ONE
7. Return JSON with recommend_return_flight only (outbound fields = null)

### ONE-WAY DOUBLE SEARCH (type="one_way", directions="both"):
4. Call BOTH searches in a SINGLE turn (parallel tool calls):
   - search_flights with flight_type=2, outbound_date=start_date, outbound_times=converted_outbound_times
   - search_flights with flight_type=2, outbound_date=end_date, departure_id/arrival_id SWAPPED, outbound_times=converted_return_times
5. Apply No-Results Fallback independently for each search if needed
6. Analyze and choose the best outbound flight + best return flight
7. Return JSON with BOTH recommend_outbound_flight and recommend_return_flight

### ROUND-TRIP FLOW (type="round_trip", directions="both"):
4. Call search_flights with flight_type=1, outbound_times and return_times (DO NOT pass departure_token)
5. Apply No-Results Fallback if needed
6. From outbound results, rank the flights by suitability. Note the TOP 2 candidates and their departure_tokens.
7. Call search_flights AGAIN with ALL the SAME required params (departure_id, arrival_id, outbound_date, return_date, flight_type, adults, children, infants_in_seat, infants_on_lap, travel_class, currency) PLUS departure_token of the BEST outbound. Do NOT pass outbound_times/return_times.
8. Check return results:
   8a. If results exist → choose the best return flight → go to step 9
   8b. If results are EMPTY → RETRY with the 2ND BEST outbound's departure_token
       - If results exist now → choose the best return flight. In recommend_return_note, mention: "Return search with [1st outbound flight_number] returned no results; switched to [2nd outbound flight_number]"
       - If still EMPTY → FALL BACK to ONE-WAY DOUBLE SEARCH (with outbound_times/return_times if provided):
         * Call search_flights with flight_type=2, outbound_date=start_date for outbound, with the ORIGINAL converted outbound_times
         * Call search_flights with flight_type=2, outbound_date=end_date, airports SWAPPED for return, with the ORIGINAL converted return_times as outbound_times
         * Apply No-Results Fallback for each if needed (widen time then remove time)
         * In recommend_return_note, explain: "Round-trip return search returned no results for any outbound flight; fell back to separate one-way searches"
         * Set type="one_way" in the output JSON (since actual booking is now two one-way tickets)
9. Return the final JSON

## Tools

### search_airports (use ONLY when IATA codes are not already known)
- lat, lon: Coordinates of the city
- radius_km: Search radius (default 100)
- limit: Max results (default 5)

### search_flights
Required parameters (MUST always be provided):
- departure_id: [REQUIRED] Departure airport IATA code (e.g., "SGN")
- arrival_id: [REQUIRED] Arrival airport IATA code (e.g., "HAN")
- outbound_date: [REQUIRED] YYYY-MM-DD
- flight_type: [REQUIRED] 1=Round trip, 2=One way
- adults: [REQUIRED] Number of adult passengers
- children: [REQUIRED] Number of child passengers
- infants_in_seat: [REQUIRED] Number of infants in seat
- infants_on_lap: [REQUIRED] Number of infants on lap
- travel_class: [REQUIRED] 1=Economy, 2=Premium economy, 3=Business, 4=First
- currency: [REQUIRED] Currency code

Optional parameters:
- return_date: YYYY-MM-DD (ONLY for round trips flight_type=1)
- stops: 0=Any, 1=Nonstop, 2=1 stop or fewer, 3=2 stops or fewer
- max_price: Maximum ticket price
- outbound_times: SerpApi format string (e.g., "0,23,8,9"). See conversion rules above.
- return_times: SerpApi format string. Only for round-trip (flight_type=1) first search.
- departure_token: Token from outbound search for return flights. ONLY for SECOND call in round-trip.

## Response Format

CRITICAL: If your next step is to use tool, return your response to call the tool. If you don't need to use tools anymore, Your response must be one and ONLY one valid JSON object, No text before or after, Just the raw JSON starting with { and ending with }.

EXAMPLE - FINAL OUTPUT STRUCTURE:
{
  "type": "one_way | round_trip",
  "directions": "both | outbound_only | return_only",
  "outbound_flights_found": true,
  "recommend_outbound_flight": {
    "flight_number": "VN123",
    "airline": "Vietnam Airlines",
    "departure_time": "08:00",
    "departure_airport_id": "SGN",
    "departure_airport_name": "Tan Son Nhat International Airport",
    "arrival_time": "10:00",
    "arrival_airport_id": "HAN",
    "arrival_airport_name": "Noi Bai International Airport"
  },
  "recommend_outbound_note": "Note for outbound flight",
  "return_flights_found": true,
  "recommend_return_flight": {
    "flight_number": "VN456",
    "airline": "Vietnam Airlines",
    "departure_time": "18:00",
    "departure_airport_id": "HAN",
    "departure_airport_name": "Noi Bai International Airport",
    "arrival_time": "20:00",
    "arrival_airport_id": "SGN",
    "arrival_airport_name": "Tan Son Nhat International Airport"
  },
  "recommend_return_note": "Note for return flight"
}

### Note field requirements:
- **recommend_outbound_note** MUST include: search method (round-trip / one-way), the chosen flight's price, airline, and WHY this flight was selected over others (time fit, price, stops).
  Normal example: "Round-trip search. Chose VN123 (2,600,000 VND, Vietnam Airlines, nonstop) — arrives at 10:00, fitting the requested 9:00-11:00 AM window. Other options were 30% more expensive or had layovers."
  Fallback-to-one-way example: "Originally searched as round-trip but fell back to one-way. Chose VN123 (1,200,000 VND, Vietnam Airlines, nonstop) — arrives 10:00, best price within the 9-11 AM window."
  Time-widened example: "One-way search. No flights found in 9:00-11:00 AM window; widened to 6:00 AM-2:00 PM. Chose VN125 (1,400,000 VND, VietJet, nonstop) — arrives 12:30."

- **recommend_return_note** MUST include: same info as above. If fallback was triggered, explain what happened.
  Normal example: "Round-trip return search. Chose VN456 (total round-trip: 5,200,000 VND, Vietnam Airlines) — departs 18:00, matching the preferred 4-6 PM window."
  2nd-outbound-retry example: "Return search with VN123's departure_token returned no results; retried with 2nd best outbound VN125. Chose VN456 (5,400,000 VND, Vietnam Airlines) — departs 17:30, within preferred 4-6 PM window."
  Fallback-to-one-way example: "Round-trip return search failed for both outbound options (VN123, VN125); fell back to separate one-way search. Chose VN789 (1,500,000 VND, Bamboo Airways) — departs 17:00."
  No-results example: "No return flights found despite widening time window and removing filters. Recommend booking manually via Google Flights."

NOTE: For outbound_only → set return_flights_found/recommend_return_flight/recommend_return_note to null.
For return_only → set outbound_flights_found/recommend_outbound_flight/recommend_outbound_note to null.


## Rules
- If you know the IATA codes from city names, go DIRECTLY to search_flights
- Only call search_airports when the origin/destination is ambiguous
- ALWAYS convert outbound_times/return_times from orchestrator's natural language to SerpApi format before calling search_flights
- For directions="both" (either one_way or round_trip), DO NOT output final JSON until you have results for BOTH outbound and return flights
- When No-Results Fallback is triggered, mention the adjusted time window in your recommend_note
- EVERY call to search_flights MUST include ALL required parameters. Even when using departure_token, you must still pass departure_id, arrival_id, outbound_date, return_date, flight_type, adults, etc.
"""


def _find_flight_data(flight_number: str, tool_logs: list[dict]) -> dict:
    """Find the price of a specific flight from search_flights tool results.
    Returns: {"price": int}
    """
    if not flight_number:
        return {"price": 0}

    normalized_target = flight_number.replace(" ", "").lower()
    
    # Search in REVERSE order — newest search results first
    for log in reversed(tool_logs):
        if log.get("name") != "search_flights":
            continue
        output = log.get("output", {})
        if not isinstance(output, dict):
            continue

        flight_data = output.get("data", output)
        if not isinstance(flight_data, dict):
            continue

        normalized = {k.lower(): v for k, v in flight_data.items()}

        for group_key in ("bestflights", "otherflights"):
            groups = normalized.get(group_key) or []
            for group in groups:
                price = group.get("Price", group.get("price", 0))
                flights_list = group.get("Flights", group.get("flights", []))
                for segment in (flights_list or []):
                    seg_fn = (segment.get("FlightNumber", segment.get("flightNumber", "")) or "").replace(" ", "").lower()
                    if seg_fn == normalized_target:
                        logger.info(f"   [FLIGHT_DATA] Matched '{flight_number}': price={price}")
                        return {"price": price}

    logger.warning(f"   [FLIGHT_DATA] Could not find data for '{flight_number}'")
    return {"price": 0}


def _get_google_flights_url(tool_logs: list[dict], search_index_from_end: int = 0) -> str:
    """Get GoogleFlightsUrl from tool_logs. search_index_from_end=0 means last search call."""
    search_count = 0
    for log in reversed(tool_logs):
        if log.get("name") == "search_flights":
            if search_count == search_index_from_end:
                output = log.get("output", {})
                if isinstance(output, dict):
                    data = output.get("data", output)
                    if isinstance(data, dict):
                        # GoogleFlightsUrl is at top level of the search response
                        return data.get("GoogleFlightsUrl", data.get("googleFlightsUrl", "")) or ""
                return ""
            search_count += 1
    return ""


def _extract_alternatives_from_search(
    tool_logs: list[dict], chosen_fns: list[str],
    search_index_from_end: int = 0, max_alts: int = 2,
    direction_label: str = ""
) -> list[dict]:
    """Extract alternative flights from a specific search_flights call."""
    alternatives = []
    used_fns = set(chosen_fns)
    search_count = 0
    
    for log in reversed(tool_logs):
        if log.get("name") != "search_flights":
            continue
        if search_count != search_index_from_end:
            search_count += 1
            continue
            
        output = log.get("output", {})
        if not isinstance(output, dict):
            break
        flight_data = output.get("data", output)
        if not isinstance(flight_data, dict):
            break
            
        normalized = {k.lower(): v for k, v in flight_data.items()}
        
        for group in (normalized.get("bestflights", []) or []) + (normalized.get("otherflights", []) or []):
            if len(alternatives) >= max_alts:
                break
            price = group.get("Price", group.get("price", 0))
            total_dur = group.get("TotalDuration", group.get("totalDuration", 0))
            flights_list = group.get("Flights", group.get("flights", []))
            if not flights_list:
                continue
            first_seg = flights_list[0]
            fn = first_seg.get("FlightNumber", first_seg.get("flightNumber", ""))
            code = fn.replace(" ", "").lower()
            if code in used_fns:
                continue
            
            dep_airport = first_seg.get("DepartureAirport", first_seg.get("departureAirport", {}))
            arr_airport = flights_list[-1].get("ArrivalAirport", flights_list[-1].get("arrivalAirport", {}))
            
            dep_id = dep_airport.get("Id", dep_airport.get("id", "")) if isinstance(dep_airport, dict) else ""
            dep_time = dep_airport.get("Time", dep_airport.get("time", "")) if isinstance(dep_airport, dict) else ""
            arr_id = arr_airport.get("Id", arr_airport.get("id", "")) if isinstance(arr_airport, dict) else ""
            arr_time = arr_airport.get("Time", arr_airport.get("time", "")) if isinstance(arr_airport, dict) else ""
            airline = first_seg.get("Airline", first_seg.get("airline", ""))
            stops = len(flights_list) - 1
            
            alt = {
                "flight_number": fn,
                "airline": airline,
                "departure_time": dep_time,
                "departure_airport_id": dep_id,
                "arrival_time": arr_time,
                "arrival_airport_id": arr_id,
                "price": price,
                "total_duration_min": total_dur,
                "stops": stops,
            }
            if direction_label:
                alt["direction"] = direction_label
            alternatives.append(alt)
            used_fns.add(code)
        break
    
    return alternatives


def _extract_total_price_and_enrich(flight_result: dict, tool_logs: list[dict]) -> int:
    """Extract total flight price and enrich flight object with google_flights_url and alternatives."""
    flight_type = flight_result.get("type", "one_way")
    directions = flight_result.get("directions", "both")
    
    outbound_price = 0
    return_price = 0
    
    outbound_flight = flight_result.get("recommend_outbound_flight")
    return_flight = flight_result.get("recommend_return_flight")
    
    if outbound_flight:
        outbound_fn = outbound_flight.get("flight_number", "")
        data = _find_flight_data(outbound_fn, tool_logs)
        outbound_price = data["price"]
    
    if return_flight:
        return_fn = return_flight.get("flight_number", "")
        data = _find_flight_data(return_fn, tool_logs)
        return_price = data["price"]
    
    if flight_type == "round_trip":
        total = return_price if return_price else outbound_price
    elif directions == "both":
        total = outbound_price + return_price
    else:
        total = outbound_price or return_price
    
    # Extract google_flights_url and alternatives based on flight type
    chosen_fns = []
    if outbound_flight:
        chosen_fns.append(outbound_flight.get("flight_number", "").replace(" ", "").lower())
    if return_flight:
        chosen_fns.append(return_flight.get("flight_number", "").replace(" ", "").lower())
    
    if flight_type == "round_trip":
        # Roundtrip: outbound search is first (index=1 from end), return search is last (index=0)
        # The google_flights_url from the OUTBOUND search is the main link
        # Count how many search_flights calls there are
        search_count = sum(1 for log in tool_logs if log.get("name") == "search_flights")
        outbound_idx = search_count - 1 if search_count > 1 else 0
        
        flight_result["google_flights_url"] = _get_google_flights_url(tool_logs, outbound_idx)
        # Only show alternatives from the outbound search
        flight_result["alternatives"] = _extract_alternatives_from_search(
            tool_logs, chosen_fns, search_index_from_end=outbound_idx
        )
    elif directions == "both":
        # Two one-way searches: outbound (older) and return (newer)
        outbound_url = _get_google_flights_url(tool_logs, search_index_from_end=1)
        return_url = _get_google_flights_url(tool_logs, search_index_from_end=0)
        if outbound_flight:
            outbound_flight["google_flights_url"] = outbound_url
        if return_flight:
            return_flight["google_flights_url"] = return_url
        
        outbound_alts = _extract_alternatives_from_search(
            tool_logs, chosen_fns, search_index_from_end=1, direction_label="outbound"
        )
        return_alts = _extract_alternatives_from_search(
            tool_logs, chosen_fns, search_index_from_end=0, direction_label="return"
        )
        flight_result["alternatives"] = outbound_alts + return_alts
    else:
        # Single direction
        flight_result["google_flights_url"] = _get_google_flights_url(tool_logs)
        flight_result["alternatives"] = _extract_alternatives_from_search(tool_logs, chosen_fns)

    logger.info(f"   [FLIGHT_AGENT] Extracted totalPrice: {total}, alts={len(flight_result.get('alternatives', []))}")
    return total


async def flight_agent_node(state: GraphState) -> dict[str, Any]:
    """Flight Agent — Airport + flight search. Pipeline or standalone mode."""
    logger.info("=" * 60)
    logger.info("✈️ [FLIGHT_AGENT] Node entered")

    plan = state.get("macro_plan", {})
    current_plan = state.get("current_plan", {})
    plan_context = current_plan.get("plan_context", {})
    mobility_plan = plan.get("mobility_plan", {})

    # Unified task request — from Orchestrator (pipeline) or Intent (standalone)
    agent_requests = plan.get("agent_requests", {})
    agent_request = agent_requests.get("flight", "")

    if not agent_request:
        logger.info("   No agent_request for flight → skip")
        return {
            "agent_outputs": {"flight_agent": {"flights_found": False, "skipped": True}},
            "messages": [AIMessage(content="[Flight Agent] No flight search needed")],
        }

    is_pipeline = bool(plan.get("task_list"))
    logger.info(f"   Mode: {'PIPELINE' if is_pipeline else 'STANDALONE'}")

    flight_result = {}

    try:
        # Ensure direction defaults are explicit for the LLM
        task_lower = agent_request.lower()
        direction_hint = ""
        if "outbound_only" not in task_lower and "return_only" not in task_lower and "one direction" not in task_lower:
            if "directions" not in task_lower and "direction" not in task_lower:
                direction_hint = '\n\nIMPORTANT: The user did not specify a direction. Default to type="one_way", directions="both" — search BOTH outbound AND return as two separate one-way flights.'

        # Build the human message with plan_context + agent_request
        human_content = f"""Plan context:
{json.dumps(plan_context, indent=2, ensure_ascii=False)}

Mobility plan:
{json.dumps(mobility_plan, indent=2, ensure_ascii=False) if mobility_plan else "N/A"}

Task:
{agent_request}{direction_hint}"""

        llm_messages = [
            SystemMessage(content=FLIGHT_AGENT_SYSTEM),
            HumanMessage(content=human_content),
        ]

        result, tool_logs = await _run_agent_with_tools(
            llm=llm_flight, messages=llm_messages,
            tools=[search_airports, search_flights], max_iterations=10,
            agent_name="FLIGHT_AGENT",
        )
        flight_result = _extract_json(result.content)
        flight_result["tools"] = tool_logs

        # Extract totalPrice and links programmatically from search results
        flight_result["totalPrice"] = _extract_total_price_and_enrich(flight_result, tool_logs)

        # Mock
        # flight_result = _extract_json(FLIGHT_AGENT_MOCK)

    except Exception as e:
        logger.error(f"   ❌ Flight Agent error: {e}", exc_info=True)
        flight_result = {"flights_found": False, "error": str(e)}

    # --- Phase 2: Resolve airport names to placeIds (deduplicated) ---
    if not flight_result.get("error"):
        import asyncio as _aio
        # Collect all unique airport names
        airport_names: dict[str, None] = {}  # use dict as ordered set
        for flight_key in ("recommend_outbound_flight", "recommend_return_flight"):
            flight_info = flight_result.get(flight_key)
            if not flight_info:
                continue
            for prefix in ("departure", "arrival"):
                name = flight_info.get(f"{prefix}_airport_name", "")
                if name:
                    airport_names[name] = None

        # Resolve unique names in parallel
        resolved_airports: dict[str, str] = {}  # name → placeId
        if airport_names:
            async def _resolve_airport(name: str) -> tuple[str, str | None]:
                try:
                    res = await resolve_single_place(name)
                    pid = res.get("placeId") if res else None
                    if pid:
                        logger.info(f"   ✅ Airport '{name}' → placeId={pid}")
                    return name, pid
                except Exception as e:
                    logger.error(f"   ⚠️ Airport resolve failed for '{name}': {e}")
                    return name, None

            results = await _aio.gather(*[_resolve_airport(n) for n in airport_names])
            for name, pid in results:
                if pid:
                    resolved_airports[name] = pid

        # Apply resolved placeIds back to both flight objects
        for flight_key in ("recommend_outbound_flight", "recommend_return_flight"):
            flight_info = flight_result.get(flight_key)
            if not flight_info:
                continue
            for prefix in ("departure", "arrival"):
                name = flight_info.get(f"{prefix}_airport_name", "")
                if name in resolved_airports:
                    flight_info[f"{prefix}_airport_placeId"] = resolved_airports[name]

    logger.info("✈️ [FLIGHT_AGENT] Node completed")
    logger.info("=" * 60)

    if "tools" in flight_result:
        flight_result.pop("tools", None)

    return {
        "agent_outputs": {"flight_agent": flight_result},
        "messages": [AIMessage(content=f"[Flight Agent] {flight_result.get('search_summary', 'Flight search completed')}")],
    }
