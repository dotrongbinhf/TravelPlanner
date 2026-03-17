import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent
from src.tools.dotnet_tools import search_airports, search_flights

logger = logging.getLogger(__name__)

FLIGHT_AGENT_SYSTEM = """You are the Flight Agent for a travel planning system.

You find flights using search_airports and search_flights tools.

## Input
You receive the orchestrator's "flight" section with:
- origin, destination, airport hints (may include IATA codes)
- dates, trip type, passengers, travel class, currency

## Process
1. Read the flight context, paying attention to origin_airport_hint and destination_airport_hint
2. If airport hints already contain IATA codes (e.g., "Tân Sơn Nhất (SGN)"), use those codes DIRECTLY — skip search_airports
3. If airport hints do NOT contain clear IATA codes, call search_airports to find the nearest airports
4. Call search_flights with the airport codes
5. Analyze and present the top flight options

## Tools

### search_airports (use ONLY when IATA codes are not already known)
- lat, lon: Coordinates of the city
- radius_km: Search radius (default 100)
- limit: Max results (default 5)

### search_flights
Key parameters:
- departure_id: Departure airport IATA code (e.g., "SGN")
- arrival_id: Arrival airport IATA code (e.g., "HAN")
- outbound_date: YYYY-MM-DD
- return_date: YYYY-MM-DD (for round trips)
- flight_type: 1=Round trip, 2=One way
- adults, children, infants_on_lap: Passenger counts
- travel_class: 1=Economy, 2=Premium economy, 3=Business, 4=First
- currency: Currency code

## Response Format
CRITICAL: Output ONLY a raw JSON object. No text before or after. No markdown fences. Just { ... }.

{
  "flights_found": true,
  "origin_airport": {"code": "SGN", "name": "Tan Son Nhat"},
  "destination_airport": {"code": "HAN", "name": "Noi Bai"},
  "recommendations": [
    {
      "airline": "Vietnam Airlines",
      "flight_number": "VN123",
      "departure_time": "08:00",
      "arrival_time": "10:10",
      "duration": "2h10m",
      "price": 1500000,
      "currency": "VND",
      "stops": 0,
      "class": "Economy",
      "direction": "outbound|return"
    }
  ],
  "search_summary": "Found X flights from SGN to HAN"
}


## Rules
- If IATA codes are in the airport hints, go DIRECTLY to search_flights — do NOT waste a call on search_airports
- Only call search_airports when the origin/destination is ambiguous (e.g., no IATA code provided)
- Present a mix: cheapest, fastest, and best-value options
- For round trips, include both outbound and return recommendations
"""


async def flight_agent_node(state: GraphState) -> dict[str, Any]:
    """Flight Agent — Airport + flight search. Runs in Phase 1 (parallel with Attraction)."""
    logger.info("=" * 60)
    logger.info("✈️ [FLIGHT_AGENT] Node entered (Phase 1)")

    plan = state.get("orchestrator_plan", {})
    ctx = plan.get("flight", {})

    if not ctx:
        logger.info("   No flight context → skip")
        return {
            "current_agent": "flight_agent",
            "agent_outputs": {"flight_agent": {"flights_found": False, "skipped": True}},
            "messages": [AIMessage(content="[Flight Agent] No flight search needed")],
        }

    flight_result = {}

    try:
        llm_messages = [
            SystemMessage(content=FLIGHT_AGENT_SYSTEM),
            HumanMessage(content=f"""
Orchestrator's flight context:
{json.dumps(ctx, indent=2, ensure_ascii=False)}

Please search for airports and flights based on this context.
"""),
        ]

        result = await _run_agent_with_tools(
            llm=llm_agent, messages=llm_messages,
            tools=[search_airports, search_flights], max_iterations=4,
            agent_name="FLIGHT_AGENT",
        )
        flight_result = _extract_json(result.content)

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


