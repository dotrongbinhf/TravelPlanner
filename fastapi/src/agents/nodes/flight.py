import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.tools.dotnet_tools import search_airports, search_flights
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import settings

logger = logging.getLogger(__name__)

llm_flight = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)

FLIGHT_AGENT_MOCK= {
  "type": "round_trip",
  "directions": "both",
  "outbound_flights_found": True,
  "recommend_outbound_flight": {
    "flight_number": "VN 240",
    "departure_time": "07:00",
    "departure_airport_name": "Tan Son Nhat International Airport",
    "arrival_time": "09:10",
    "arrival_airport_name": "Noi Bai International Airport"
  },
  "recommend_outbound_note": "This flight arrives at 09:10, fitting perfectly within your requested arrival window of 9:00 AM - 11:00 AM, allowing you to start your Hanoi exploration as planned.",
  "return_flights_found": True,
  "recommend_return_flight": {
    "flight_number": "VN 257",
    "departure_time": "17:30",
    "departure_airport_name": "Noi Bai International Airport",
    "arrival_time": "19:40",
    "arrival_airport_name": "Tan Son Nhat International Airport"
  },
  "recommend_return_note": "This flight departs at 17:30, which aligns well with your preference for an afternoon flight (4:00 PM - 6:00 PM) on your last day, giving you time for final activities or shopping."
}

FLIGHT_AGENT_SYSTEM = """You are the Flight Agent for a travel planning system.

You find flights using search_airports and search_flights tools.

## Input
You receive two pieces of context from the Orchestrator:
1. **plan_context**: Shared trip info (departure city, destination, dates, passengers, budget, currency, mobility_plan)
2. **flight context**: Flight-specific info (airport hints, infants_in_seat/infants_on_lap, user preferences including type, directions, travel_class, max_price, outbound_times, return_times)

## Determine Search Flow

Read `type` and `directions` from user_flight_preferences:
- **type**: "one_way" (default) or "round_trip"
- **directions**: "both" (default), "outbound_only", or "return_only"

| type       | directions     | Flow                          |
|-----------|----------------|-------------------------------|
| one_way   | both           | ONE-WAY DOUBLE SEARCH         |
| one_way   | outbound_only  | ONE-WAY OUTBOUND ONLY         |
| one_way   | return_only    | ONE-WAY RETURN ONLY           |
| round_trip| both           | ROUND-TRIP FLOW               |

## Process
1. Read both plan_context and flight context carefully
2. Determine airport IATA codes:
  - If airport hints already contain IATA codes (e.g., "Tân Sơn Nhất (SGN)"), extract and use those codes DIRECTLY — skip search_airports if confident
  - If airport hints do NOT contain clear IATA codes, call search_airports to find the nearest airports
3. Map user preferences and plan_context to search_flights parameters:
  - travel_class: "economy"→1, "premium_economy"→2, "business"→3, "first"→4
  - For round_trip: outbound_date = plan_context.start_date, return_date = plan_context.end_date
  - For one_way: outbound_date = plan_context.start_date (outbound) or end_date (return), do NOT pass return_date
  - max_price: pass if user specified
  - **Convert outbound_times and return_times** to SerpApi format (see below)

## Converting Time Preferences to SerpApi Format

The Orchestrator provides:
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
       - If still EMPTY → FALL BACK to ONE-WAY DOUBLE SEARCH:
         * Call search_flights with flight_type=2, outbound_date=start_date for outbound
         * Call search_flights with flight_type=2, outbound_date=end_date, airports SWAPPED for return
         * Apply No-Results Fallback for each if needed
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
    "departure_time": "08:00",
    "departure_airport_name": "Tan Son Nhat International Airport",
    "arrival_time": "10:00",
    "arrival_airport_name": "Noi Bai International Airport"
  },
  "recommend_outbound_note": "Note for outbound flight",
  "return_flights_found": true,
  "recommend_return_flight": {
    "flight_number": "VN456",
    "departure_time": "18:00",
    "departure_airport_name": "Noi Bai International Airport",
    "arrival_time": "20:00",
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
- If IATA codes are in the airport hints, go DIRECTLY to search_flights — do NOT waste a call on search_airports
- Only call search_airports when the origin/destination is ambiguous (e.g., no IATA code provided)
- ALWAYS convert outbound_times/return_times from orchestrator's natural language to SerpApi format before calling search_flights
- For directions="both" (either one_way or round_trip), DO NOT output final JSON until you have results for BOTH outbound and return flights
- When No-Results Fallback is triggered, mention the adjusted time window in your recommend_note
- EVERY call to search_flights MUST include ALL required parameters. Even when using departure_token, you must still pass departure_id, arrival_id, outbound_date, return_date, flight_type, adults, etc.
"""


def _find_price_for_flight(flight_number: str, tool_logs: list[dict]) -> int:
    """Find the price of a specific flight from search_flights tool results.
    
    Searches through BestFlights and OtherFlights in all search_flights tool calls,
    matching the recommended flight_number against the FlightSegmentDto.FlightNumber.
    
    Returns the Price of the matching FlightGroupDto, or 0 if not found.
    """
    if not flight_number:
        return 0
    
    # Normalize flight number for matching (remove spaces, lowercase)
    normalized_target = flight_number.replace(" ", "").lower()
    
    for log in tool_logs:
        if log.get("name") != "search_flights":
            continue
        output = log.get("output", {})
        if not isinstance(output, dict):
            continue
        
        # Check both BestFlights and OtherFlights
        for group_key in ("BestFlights", "OtherFlights"):
            groups = output.get(group_key) or []
            for group in groups:
                price = group.get("Price", 0)
                for segment in (group.get("Flights") or []):
                    seg_fn = (segment.get("FlightNumber") or "").replace(" ", "").lower()
                    if seg_fn == normalized_target:
                        return price
    
    return 0


def _extract_total_price(flight_result: dict, tool_logs: list[dict]) -> int:
    """Extract total flight price from tool_logs based on the LLM's chosen flights.
    
    Logic:
    - one_way + both: sum outbound price + return price (2 separate searches)
    - round_trip + both: return search price is already the total (includes outbound)
    - outbound_only / return_only: single search price
    """
    flight_type = flight_result.get("type", "one_way")
    directions = flight_result.get("directions", "both")
    
    outbound_price = 0
    return_price = 0
    
    outbound_flight = flight_result.get("recommend_outbound_flight")
    return_flight = flight_result.get("recommend_return_flight")
    
    if outbound_flight:
        outbound_fn = outbound_flight.get("flight_number", "")
        outbound_price = _find_price_for_flight(outbound_fn, tool_logs)
    
    if return_flight:
        return_fn = return_flight.get("flight_number", "")
        return_price = _find_price_for_flight(return_fn, tool_logs)
    
    if flight_type == "round_trip":
        # For round-trip, the return search result contains the combined total
        # If we have return_price, use it; otherwise fall back to outbound_price
        total = return_price if return_price else outbound_price
    elif directions == "both":
        # One-way double search: sum both legs
        total = outbound_price + return_price
    else:
        # Single direction
        total = outbound_price or return_price
    
    logger.info(f"   [FLIGHT_AGENT] Extracted totalPrice: {total} "
                f"(outbound={outbound_price}, return={return_price}, "
                f"type={flight_type}, directions={directions})")
    return total


async def flight_agent_node(state: GraphState) -> dict[str, Any]:
    """Flight Agent — Airport + flight search. Runs in Phase 1 (parallel)."""
    logger.info("=" * 60)
    logger.info("✈️ [FLIGHT_AGENT] Node entered (Phase 1)")

    plan = state.get("orchestrator_plan", {})
    plan_context = plan.get("plan_context", {})
    flight_ctx = plan.get("flight", {})

    if not flight_ctx:
        logger.info("   No flight context → skip")
        return {
            "agent_outputs": {"flight_agent": {"flights_found": False, "skipped": True}},
            "messages": [AIMessage(content="[Flight Agent] No flight search needed")],
        }

    flight_result = {}

    try:
        # Build the human message with both plan_context and flight-specific context
        human_content = f"""Plan context (shared trip info):
{json.dumps(plan_context, indent=2, ensure_ascii=False)}

Flight-specific context:
{json.dumps(flight_ctx, indent=2, ensure_ascii=False)}

Search for flights based on this context. Use the plan_context for dates, passengers, and budget info. Use the flight context for airport hints, trip type, passengers specific (infants_in_seat, infants_on_lap), and preferences."""

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

        # Extract totalPrice programmatically from search results
        flight_result["totalPrice"] = _extract_total_price(flight_result, tool_logs)

        # Mock
        # flight_result = _extract_json(FLIGHT_AGENT_MOCK)

    except Exception as e:
        logger.error(f"   ❌ Flight Agent error: {e}", exc_info=True)
        flight_result = {"flights_found": False, "error": str(e)}

    logger.info("✈️ [FLIGHT_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"flight_agent": flight_result},
        "messages": [AIMessage(content=f"[Flight Agent] {flight_result.get('search_summary', 'Flight search completed')}")],
    }
