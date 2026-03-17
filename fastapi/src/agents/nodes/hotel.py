import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent, llm_fast
from src.tools.dotnet_tools import search_hotels
from src.tools.place_resolver import resolve_place

logger = logging.getLogger(__name__)

HOTEL_AGENT_SYSTEM = """You are the Hotel Agent for a travel planning system.

You search for hotels that match the user's requirements.
You run AFTER the Attraction Agent, so you receive the actual attraction distribution to choose the best location.

## Input
You receive:
1. The orchestrator's "hotel" section with: destination, dates, guests, budget, strategy, preferred_areas
2. Attraction Agent results: a list of resolved attractions with their areas and coordinates

## Process
1. Read the hotel context from orchestrator
2. Analyze the attraction distribution — which areas have the most attractions?
3. Choose the BEST area for the hotel based on:
   - Where the MAJORITY of attractions are concentrated
   - Practical accessibility to other areas
   - The orchestrator's preferred_areas hint
   - For multi_hotel: choose a different area per night segment near that night's attractions
4. Call search_hotels with the best area
5. Recommend top hotels

## Tool: search_hotels
Key parameters:
- query: Search text with area (e.g., "Hotels in Hoàn Kiếm, Hà Nội")
- check_in_date: YYYY-MM-DD
- check_out_date: YYYY-MM-DD
- adults, children: Guest counts
- children_ages: Ages of children, comma-separated (e.g. "5,8"). REQUIRED when children > 0.
- hotel_class: Star filter ("3,4" or "4,5")
- sort_by: 3=Lowest price, 8=Highest rating

## Response Format
CRITICAL: Output ONLY a raw JSON object. No text before or after. No markdown fences. Just { ... }.

{
  "hotels_found": true,
  "strategy": "single_hotel|multi_hotel",
  "chosen_area": "Hoàn Kiếm",
  "area_reasoning": "5 of 8 attractions are in Hoàn Kiếm, and Ba Đình is just 10 min away",
  "recommendations": [
    {
      "name": "Hotel Name",
      "search_name": "Full hotel name + city (for place resolution)",
      "area": "Hoàn Kiếm",
      "check_in": "YYYY-MM-DD",
      "check_out": "YYYY-MM-DD",
      "nights": 3,
      "price_per_night": 800000,
      "total_price": 2400000,
      "currency": "VND",
      "rating": 4.5,
      "stars": 4,
      "amenities": ["WiFi", "Pool"],
      "highlights": "Why this hotel is recommended"
    }
  ],
  "search_summary": "Brief summary"
}


## Rules
- Always call search_hotels — do NOT make up hotel data
- Choose hotel area based on attraction distribution, NOT just geometric center
- For multi_hotel: run separate searches per night segment
- Include a mix of options matching the budget level
- Use exact hotel names that exist on Google Maps
"""


async def hotel_agent_node(state: GraphState) -> dict[str, Any]:
    """Hotel Agent — Searches hotels using attraction distribution data. Runs in Phase 2."""
    logger.info("=" * 60)
    logger.info("🏨 [HOTEL_AGENT] Node entered (Phase 2)")

    plan = state.get("orchestrator_plan", {})
    ctx = plan.get("hotel", {})
    agent_outputs = state.get("agent_outputs", {})
    attraction_data = agent_outputs.get("attraction_agent", {})

    if not ctx:
        logger.info("   No hotel context → skip")
        return {
            "current_agent": "hotel_agent",
            "agent_outputs": {"hotel_agent": {"hotels_found": False, "skipped": True}},
            "messages": [AIMessage(content="[Hotel Agent] No hotel search needed")],
        }

    destination = ctx.get("destination", "")
    hotel_result = {}

    # Build attraction distribution summary for the LLM
    area_distribution = attraction_data.get("area_distribution", {})
    attractions_summary = []
    for attr in attraction_data.get("attractions", []):
        summary = {
            "name": attr.get("name"),
            "day": attr.get("suggested_day"),
            "area": attr.get("area"),
        }
        loc = attr.get("location", {})
        if loc and loc.get("coordinates"):
            summary["coordinates"] = loc["coordinates"]
        attractions_summary.append(summary)

    try:
        llm_messages = [
            SystemMessage(content=HOTEL_AGENT_SYSTEM),
            HumanMessage(content=f"""
Orchestrator's hotel context:
{json.dumps(ctx, indent=2, ensure_ascii=False)}

Attraction distribution across days:
{json.dumps(area_distribution, indent=2, ensure_ascii=False)}

All resolved attractions with areas and coordinates:
{json.dumps(attractions_summary, indent=2, ensure_ascii=False)[:3000]}

Based on the attraction distribution, choose the BEST area for the hotel and search for options.
"""),
        ]

        result = await _run_agent_with_tools(
            llm=llm_agent, messages=llm_messages,
            tools=[search_hotels], max_iterations=3,
            agent_name="HOTEL_AGENT",
        )
        hotel_result = _extract_json(result.content)

        # Resolve hotel places
        recommendations = hotel_result.get("recommendations", [])
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

        for hotel in recommendations:
            search_name = hotel.get("search_name", hotel.get("name", ""))
            if search_name:
                resolved = await resolve_place(
                    place_name=search_name,
                    location_bias=location_bias,
                )
                hotel["resolved_place"] = resolved
                if resolved.get("resolved"):
                    hotel["place_id"] = resolved.get("placeId", "")
                    hotel["db_id"] = resolved.get("id", "")
                    hotel["location"] = resolved.get("location", {})

        hotel_result["resolved_count"] = sum(1 for h in recommendations if h.get("place_id"))
        logger.info(f"   Found {len(recommendations)} hotels, resolved {hotel_result['resolved_count']}")

    except Exception as e:
        logger.error(f"   ❌ Hotel Agent error: {e}", exc_info=True)
        hotel_result = {"hotels_found": False, "error": str(e)}

    logger.info("🏨 [HOTEL_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "hotel_agent",
        "current_tool": "search_hotels",
        "agent_outputs": {"hotel_agent": hotel_result},
        "messages": [AIMessage(content=f"[Hotel Agent] {hotel_result.get('search_summary', 'Hotel search completed')}")],
    }


