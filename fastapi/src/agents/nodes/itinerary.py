import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent
from src.tools.maps_tools import get_distance_matrix
from src.tools.itinerary_tools import optimize_daily_itinerary

logger = logging.getLogger(__name__)

ITINERARY_AGENT_SYSTEM = """You are the Itinerary Agent for a travel planning system.

You create optimized daily schedules from all gathered places.

## Input
You receive outputs from all previous agents:
- Attractions with locations, suggested days, durations
- Restaurants with locations, meal types, suggested days
- Hotels with location
- Flights with times (for arrival/departure day scheduling)

## Process
1. For each day, collect all places (attractions, restaurants, hotel)
2. If places have coordinates, call get_distance_matrix for travel times
3. Set time windows for each place
4. Call optimize_daily_itinerary (VRP solver) to find the optimal visit order
5. If VRP fails, create a reasonable manual schedule

## Tools

### get_distance_matrix
- origins: List of "lat,lng" strings
- destinations: List of "lat,lng" strings
- mode: "driving" (default)

### optimize_daily_itinerary
- locations: List of {name, type} dicts
- time_matrix: N×N matrix in minutes
- time_windows: List of (earliest, latest) minutes since midnight
- service_times: Duration in minutes
- start_index, end_index: Start/end location indices

## Time Window Guidelines (minutes since midnight)
- Morning: (480, 720) = 08:00-12:00
- Lunch: (660, 840) = 11:00-14:00
- Afternoon: (720, 1080) = 12:00-18:00
- Dinner: (1080, 1260) = 18:00-21:00
- Evening: (1140, 1380) = 19:00-23:00
- Hotel/flexible: (0, 1440)

## Response Format
CRITICAL: Output ONLY a raw JSON object. No text before or after. No markdown fences. Just { ... }.

{
  "daily_schedules": [
    {
      "day": 1,
      "date": "YYYY-MM-DD",
      "schedule": [
        {
          "time": "08:00",
          "duration_minutes": 60,
          "place_name": "...",
          "place_type": "attraction|restaurant|hotel|airport",
          "place_id": "google_place_id_if_available",
          "travel_to_next_minutes": 15,
          "notes": "optional"
        }
      ]
    }
  ]
}


## Rules
- RESPECT the suggested_day assignments — do NOT move places between days
- Hotel is typically start and end of each day
- Arrival day: airport → hotel → light activities
- Departure day: hotel → activities → airport
- Fit meals at appropriate times (breakfast 7-9, lunch 11-14, dinner 18-21)
"""


async def itinerary_agent_node(state: GraphState) -> dict[str, Any]:
    """Itinerary Agent — VRP-optimized daily schedules using all agent data."""
    logger.info("=" * 60)
    logger.info("📅 [ITINERARY_AGENT] Node entered (Phase 3)")

    agent_outputs = state.get("agent_outputs", {})
    plan = state.get("orchestrator_plan", {})
    attraction_ctx = plan.get("attraction", {})
    num_days = attraction_ctx.get("num_days", 3)
    start_date = attraction_ctx.get("start_date", "")

    attraction_data = agent_outputs.get("attraction_agent", {})
    restaurant_data = agent_outputs.get("restaurant_agent", {})
    hotel_data = agent_outputs.get("hotel_agent", {})
    flight_data = agent_outputs.get("flight_agent", {})

    all_attractions = attraction_data.get("attractions", [])
    all_restaurants = restaurant_data.get("restaurants", [])

    itinerary_result = {"daily_schedules": []}

    try:
        # Build compact summaries
        attraction_summaries = [{
            "name": a.get("name"),
            "category": a.get("category"),
            "duration": a.get("suggested_duration_minutes", 60),
            "time_pref": a.get("suggested_time_window", "flexible"),
            "suggested_day": a.get("suggested_day"),
            "area": a.get("area", ""),
            "coordinates": a.get("location", {}).get("coordinates") if a.get("location") else None,
        } for a in all_attractions]

        restaurant_summaries = [{
            "name": r.get("name"),
            "meal_type": r.get("meal_type"),
            "suggested_day": r.get("suggested_day"),
            "area": r.get("area", ""),
            "coordinates": r.get("location", {}).get("coordinates") if r.get("location") else None,
        } for r in all_restaurants]

        hotel_summary = {}
        recs = hotel_data.get("recommendations", [])
        if recs:
            h = recs[0]
            hotel_summary = {
                "name": h.get("name"),
                "area": h.get("area", ""),
                "coordinates": h.get("location", {}).get("coordinates") if h.get("location") else None,
            }

        llm_messages = [
            SystemMessage(content=ITINERARY_AGENT_SYSTEM),
            HumanMessage(content=f"""
Create optimized daily schedules for a {num_days}-day trip starting {start_date}.

Attractions ({len(attraction_summaries)} total):
{json.dumps(attraction_summaries, indent=2, ensure_ascii=False)[:3000]}

Restaurants ({len(restaurant_summaries)} total):
{json.dumps(restaurant_summaries, indent=2, ensure_ascii=False)[:2000]}

Hotel: {json.dumps(hotel_summary, indent=2, ensure_ascii=False)}

Flight info: {json.dumps(flight_data.get('recommendations', []), default=str, ensure_ascii=False)[:500]}

IMPORTANT: Respect the suggested_day assignments. Optimize the ORDER within each day using the tools if coordinates are available.
"""),
        ]

        result, _ = await _run_agent_with_tools(
            llm=llm_agent, messages=llm_messages,
            tools=[get_distance_matrix, optimize_daily_itinerary], max_iterations=4,
            agent_name="ITINERARY_AGENT",
        )
        itinerary_result = _extract_json(result.content)

    except Exception as e:
        logger.error(f"   ❌ Itinerary Agent error: {e}", exc_info=True)
        itinerary_result = {"error": str(e), "daily_schedules": []}

    logger.info("📅 [ITINERARY_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "itinerary_agent",
        "current_tool": "optimize_daily_itinerary",
        "agent_outputs": {"itinerary_agent": itinerary_result},
        "messages": [AIMessage(content=f"[Itinerary Agent] Created {num_days}-day schedule")],
    }


