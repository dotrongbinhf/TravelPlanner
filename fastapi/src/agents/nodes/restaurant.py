import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent, llm_fast
from src.tools.maps_tools import places_nearby_search, places_text_search_id_only
from src.tools.place_resolver import resolve_place

logger = logging.getLogger(__name__)

RESTAURANT_AGENT_SYSTEM = """You are the Restaurant Agent for a travel planning system.

You find restaurants near the planned attraction areas.
You run AFTER the Attraction Agent, so you know exactly which attractions are on which day and in which area.

## Input
You receive:
1. The orchestrator's "restaurant" section with: destination, budget, cuisine, dietary restrictions
2. Attraction Agent results: attractions grouped by day with their areas

## Process
1. Read the restaurant context and attraction distribution
2. For each day, identify the area where attractions are concentrated
3. Use places_nearby_search or places_text_search_id_only to find real restaurants IN THAT AREA
4. Suggest appropriate meals (lunch near mid-day attractions, dinner near evening attractions)

## Tools

### places_nearby_search
- lat, lng: Center point (use coordinates from attractions)
- radius: Search radius in meters (default 2000)
- place_type: "restaurant"
- keyword: Cuisine type (e.g., "Vietnamese", "seafood")

### places_text_search_id_only
- query: Text search (e.g., "phở restaurant Hoàn Kiếm Hanoi")
- location_bias: Optional "lat,lng" to prefer nearby results

## Response Format
CRITICAL: Output ONLY a raw JSON object. No text before or after. No markdown fences. Just { ... }.

{
  "restaurants": [
    {
      "name": "Exact Restaurant Name (as on Google Maps)",
      "cuisine": "Vietnamese|Seafood|International|...",
      "meal_type": "breakfast|lunch|dinner|snack|cafe",
      "price_range": "$|$$|$$$",
      "description": "Brief description",
      "suggested_day": 1,
      "area": "Hoàn Kiếm",
      "near_attraction": "Name of nearby attraction"
    }
  ],
  "notes": "Dining tips for the destination"
}


## Rules
- At least 2 meals per day (lunch + dinner), optionally breakfast
- Restaurants MUST be in the SAME AREA as that day's attractions
- Use at least one search tool — do NOT rely purely on LLM memory
- Match budget level and dietary restrictions
- Use EXACT restaurant names findable on Google Maps
"""


async def restaurant_agent_node(state: GraphState) -> dict[str, Any]:
    """Restaurant Agent — Finds restaurants near attraction areas. Runs in Phase 2."""
    logger.info("=" * 60)
    logger.info("🍽️ [RESTAURANT_AGENT] Node entered (Phase 2)")

    plan = state.get("orchestrator_plan", {})
    ctx = plan.get("restaurant", {})
    agent_outputs = state.get("agent_outputs", {})
    attraction_data = agent_outputs.get("attraction_agent", {})

    if not ctx:
        logger.info("   No restaurant context → skip")
        return {
            "current_agent": "restaurant_agent",
            "agent_outputs": {"restaurant_agent": {"restaurants": [], "skipped": True}},
            "messages": [AIMessage(content="[Restaurant Agent] No restaurant search needed")],
        }

    destination = ctx.get("destination", "")
    restaurant_result = {}

    # Build per-day attraction areas for restaurant proximity
    area_distribution = attraction_data.get("area_distribution", {})
    attractions_by_day = {}
    for attr in attraction_data.get("attractions", []):
        day = attr.get("suggested_day", 0)
        if day not in attractions_by_day:
            attractions_by_day[day] = []
        summary = {
            "name": attr.get("name"),
            "area": attr.get("area"),
        }
        loc = attr.get("location", {})
        if loc and loc.get("coordinates"):
            summary["coordinates"] = loc["coordinates"]
        attractions_by_day[day].append(summary)

    try:
        llm_messages = [
            SystemMessage(content=RESTAURANT_AGENT_SYSTEM),
            HumanMessage(content=f"""
Orchestrator's restaurant context:
{json.dumps(ctx, indent=2, ensure_ascii=False)}

Attractions by day (search restaurants NEAR these areas):
{json.dumps(attractions_by_day, indent=2, ensure_ascii=False, default=str)[:3000]}

Area distribution summary:
{json.dumps(area_distribution, indent=2, ensure_ascii=False)}

Find restaurants in the SAME AREA as each day's attractions.
Use the search tools to find real restaurants.
"""),
        ]

        result, _ = await _run_agent_with_tools(
            llm=llm_agent, messages=llm_messages,
            tools=[places_nearby_search, places_text_search_id_only], max_iterations=4,
            agent_name="RESTAURANT_AGENT",
        )
        restaurant_result = _extract_json(result.content)

        # Resolve restaurant places
        location_bias = None
        if destination:
            try:
                coord_msg = [
                    SystemMessage(content='Return ONLY JSON: {"lat": 0.0, "lng": 0.0}'),
                    HumanMessage(content=f"Coordinates of {destination}?"),
                ]
                coord_res = await llm_fast.ainvoke(coord_msg)
                coords = _extract_json(coord_res.content)
                location_bias = f"{coords['lat']},{coords['lng']}"
            except Exception:
                pass

        restaurants = restaurant_result.get("restaurants", [])
        for rest in restaurants:
            name = rest.get("name", "")
            if name:
                resolved = await resolve_place(
                    place_name=f"{name} {destination}",
                    location_bias=location_bias,
                )
                rest["resolved_place"] = resolved
                if resolved.get("resolved"):
                    rest["place_id"] = resolved.get("placeId", "")
                    rest["db_id"] = resolved.get("id", "")
                    rest["location"] = resolved.get("location", {})

        restaurant_result["resolved_count"] = sum(1 for r in restaurants if r.get("place_id"))
        logger.info(f"   Found {len(restaurants)} restaurants, resolved {restaurant_result['resolved_count']}")

    except Exception as e:
        logger.error(f"   ❌ Restaurant Agent error: {e}", exc_info=True)
        restaurant_result = {"error": str(e), "restaurants": []}

    logger.info("🍽️ [RESTAURANT_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "restaurant_agent",
        "current_tool": "place_resolver",
        "agent_outputs": {"restaurant_agent": restaurant_result},
        "messages": [AIMessage(content=f"[Restaurant Agent] Found {len(restaurant_result.get('restaurants', []))} restaurants")],
    }


