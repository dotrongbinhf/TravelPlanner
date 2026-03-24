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

FLIGHT_AGENT_SYSTEM = """You are the Flight Agent for a travel planning system.

You find flights using search_airports and search_flights tools.

## Input
You receive two pieces of context from the Orchestrator:
1. **plan_context**: Shared trip info (departure city, destination, dates, passengers, budget, currency, mobility_plan)
2. **flight context**: Flight-specific info (airport hints, infants_in_seat/infants_on_lap, user preferences like type(one_way/round_trip), travel_class, max_price, preferred times)

## Process
1. Read both plan_context and flight context carefully
2. Determine airport IATA codes:
  - If airport hints already contain IATA codes (e.g., "Tân Sơn Nhất (SGN)"), extract and use those codes DIRECTLY — skip search_airports if confident
  - If airport hints do NOT contain clear IATA codes, call search_airports to find the nearest airports
3. Map user preferences and plan_context to search_flights parameters:
  - travel_class: "economy"→1, "premium_economy"→2, "business"→3, "first"→4
  - trip_type: "round_trip"→flight_type=1, "one_way"→flight_type=2
  - For round_trip: outbound_date = plan_context.start_date, return_date = plan_context.end_date
  - For one_way: outbound_date = plan_context.start_date, do NOT pass return_date
  - max_price: pass if user specified

### ONE-WAY FLOW:
4. Call search_flights with the correct parameters
5. From the results. Analyze all flights considering user preferences (budget, timing, duration, stops) and the plan context, then return the most suitable ONE. Prioritize flights from best_flights but pick whichever truly fits best.
6. Return the final JSON.

### ROUND-TRIP FLOW (2-step):
4. Call search_flights with the correct parameters (DO NOT pass departure_token for the first search)
5. From the outbound results:
   - Build outbound_flights list from ALL results (best_flights first, then other_flights)
   - Analyze all flights considering user preferences and plan context, then choose the most suitable ONE (prioritize best_flights but pick whichever truly fits best)
6. Call search_flights AGAIN with the SAME parameters PLUS the departure_token extracted from the recommended outbound flight in step 5
   - This retrieves return flight options specifically for the recommended outbound
7. From the return results:
   - Build return_flights list from ALL results (best_flights first, then other_flights)
   - Analyze and choose ONE flight as "recommended": true based on mobility_plan compatibility
   - Prioritize best_flights, consider timing (late activities on last day → late flight, etc.)
8. Return the final JSON.

## Tools

### search_airports (use ONLY when IATA codes are not already known)
- lat, lon: Coordinates of the city
- radius_km: Search radius (default 100)
- limit: Max results (default 5)

### search_flights
- departure_id: Departure airport IATA code (e.g., "SGN")
- arrival_id: Arrival airport IATA code (e.g., "HAN")
- outbound_date: YYYY-MM-DD
- return_date: YYYY-MM-DD (ONLY and REQUIRED for round trips, flight_type=1. Do NOT provide for one-way flights)
- flight_type: 1=Round trip, 2=One way
- adults: Number of adult passengers
- children: Number of child passengers
- infants_in_seat: Number of infants in seat
- infants_on_lap: Number of infants on lap
- travel_class: 1=Economy, 2=Premium economy, 3=Business, 4=First
- currency: Currency code
- stops: 0=Any, 1=Nonstop, 2=1 stop or fewer, 3=2 stops or fewer
- max_price: Maximum ticket price
- departure_token: Token from outbound search to retrieve return flights. ONLY use this for the SECOND call in round-trip flow.

## Response Format

CRITICAL: If your next step is to use tool, return your response to call the tool. If you don't need to use tools anymore, Your response must be one and ONLY one valid JSON object, No text before or after, Just the raw JSON starting with { and ending with }.

EXAMPLE - FINAL OUTPUT STRUCTURE:
{
  "type": "one_way | round_trip",
  "outbound_flights_found": true,
  "recommend_outbound_flight": {
    "flight_number": "VN123",
    "departure_time": "08:00",
    "departure_airport_name": "Tan Son Nhat International Airport",
    "arrival_time": "10:00",
    "arrival_airport_name": "Noi Bai International Airport",
  },
  "recommend_outbound_note": "The reason why you choose this outbound flight",
  "return_flights_found": true,
  "recommend_return_flight": {
    "flight_number": "VN456",
    "departure_time": "18:00",
    "departure_airport_name": "Noi Bai International Airport",
    "arrival_time": "20:00",
    "arrival_airport_name": "Tan Son Nhat International Airport",
  },
  "recommend_return_note": "The reason why you choose this return flight",
}

## Rules
- If IATA codes are in the airport hints, go DIRECTLY to search_flights — do NOT waste a call on search_airports
- Only call search_airports when the origin/destination is ambiguous (e.g., no IATA code provided)
- In round-trip type, DO NOT output your final JSON response until you have received the results of the SECOND tool call. If you only see outbound flights, you are NOT FINISHED. You must call search_flights again!
"""

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
            "current_agent": "flight_agent",
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
            tools=[search_airports, search_flights], max_iterations=6,
            agent_name="FLIGHT_AGENT",
        )
        flight_result = _extract_json(result.content)
        flight_result["tools"] = tool_logs

    except Exception as e:
        logger.error(f"   ❌ Flight Agent error: {e}", exc_info=True)
        flight_result = {"flights_found": False, "error": str(e)}

    logger.info("✈️ [FLIGHT_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "flight_agent",
        "current_tool": "search_flights",
        "agent_outputs": {"flight_agent": flight_result},
        "messages": [AIMessage(content=f"[Flight Agent] {flight_result.get('search_summary', 'Flight search completed')}")],
    }
