import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent, llm_fast
from src.tools.search_tools import tavily_search
from src.tools.place_resolver import resolve_place

logger = logging.getLogger(__name__)

ATTRACTION_AGENT_SYSTEM = """You are the Attraction Agent for a travel planning system.

You suggest tourist attractions and are one of the FIRST agents to run.
Your output determines where Hotel and Restaurant agents will search.

## Input
You receive the orchestrator's "attraction" section with:
- destination, dates, interests, pace, budget, travelers
- areas_per_day with daily area assignments and themes
- must_visit places and places_to_avoid

## Process
1. Read the attraction context carefully
2. Use your LLM knowledge to suggest attractions for EACH DAY following the area assignments
3. Use tavily_search ONLY to discover NEW, trending, or recently updated attractions that your training data might not include (e.g., newly opened museums, seasonal festivals, temporary exhibitions)
4. Do NOT use tavily_search for getting place details — that is handled automatically by the system's place_resolver after you respond
5. Return with EXACT place names findable on Google Maps

NOTE: After you respond, the system will automatically call place_resolver for each attraction.
This resolves the place on Google Maps, fetches detailed info (address, lat/lng, opening hours, ratings), and saves it to the database.
You do NOT need to worry about fetching details — just provide accurate place names.

## Tool: tavily_search (optional — for discovering new/trending places)
- query: Search text (e.g., "new attractions Hanoi 2026", "best cafes Hoàn Kiếm 2026")
- max_results: default 5
- Use this when: the destination may have new/trendy spots your knowledge doesn't cover
- Do NOT use this for: getting details about well-known places

## Response Format
CRITICAL: Output ONLY a raw JSON object. No text before or after. No markdown fences. Just { ... }.

{
  "destination": "Hanoi",
  "attractions": [
    {
      "name": "Exact Place Name (as on Google Maps)",
      "category": "culture|nature|adventure|food|nightlife|shopping|landmark|temple|museum|park",
      "suggested_duration_minutes": 90,
      "suggested_time_window": "morning|afternoon|evening|flexible",
      "suggested_day": 1,
      "area": "Hoàn Kiếm",
      "description": "Brief description and why it matches interests",
      "priority": "must_visit|recommended|optional",
      "estimated_cost": "free|$|$$|$$$"
    }
  ],
  "daily_summary": {
    "day_1": "Old Quarter and Hoàn Kiếm Lake exploration",
    "day_2": "Historical landmarks in Ba Đình"
  },
  "notes": "Any relevant tips"
}


## Rules
- Suggest 3-5 attractions per day depending on pace (relaxed=3, moderate=4, packed=5-6)
- Arrival day and departure day should have FEWER attractions
- STRICTLY follow the area assignments — attractions must be in or very near the assigned area
- Use EXACT place names that exist on Google Maps (they will be resolved to PlaceIds automatically)
- Include must_visit places from user
- Exclude places_to_avoid
- Consider the travelers (children → kid-friendly places, elderly → accessible places)
- Consider budget_level for paid attractions
"""


async def attraction_agent_node(state: GraphState) -> dict[str, Any]:
    """Attraction Agent — LLM-first suggestion + place resolution. Runs in Phase 1."""
    logger.info("=" * 60)
    logger.info("🏛️ [ATTRACTION_AGENT] Node entered (Phase 1)")

    plan = state.get("orchestrator_plan", {})
    ctx = plan.get("attraction", {})

    if not ctx:
        logger.info("   No attraction context → skip")
        return {
            "current_agent": "attraction_agent",
            "agent_outputs": {"attraction_agent": {"attractions": [], "skipped": True}},
            "messages": [AIMessage(content="[Attraction Agent] No attraction context provided")],
        }

    destination = ctx.get("destination", "")
    attraction_result = {}

    try:
        llm_messages = [
            SystemMessage(content=ATTRACTION_AGENT_SYSTEM),
            HumanMessage(content=f"""
Orchestrator's attraction context:
{json.dumps(ctx, indent=2, ensure_ascii=False)}

Please suggest tourist attractions following the per-day area plan.
Use your knowledge about {destination}. Provide EXACT place names findable on Google Maps.
"""),
        ]

        result = await _run_agent_with_tools(
            llm=llm_agent, messages=llm_messages,
            tools=[tavily_search], max_iterations=3,
            agent_name="ATTRACTION_AGENT",
        )
        attraction_result = _extract_json(result.content)

        # Resolve all attractions via place resolver
        attractions = attraction_result.get("attractions", [])
        location_bias = None
        if destination:
            try:
                coord_msg = [
                    SystemMessage(content='Return ONLY JSON: {"lat": 0.0, "lng": 0.0}'),
                    HumanMessage(content=f"Coordinates of {destination}?"),
                ]
                coord_result = await llm_fast.ainvoke(coord_msg)
                coords = _extract_json(coord_result.content)
                location_bias = f"{coords['lat']},{coords['lng']}"
            except Exception:
                pass

        resolved_attractions = []
        for attr in attractions:
            place_name = attr.get("name", "")
            if place_name:
                logger.info(f"   Resolving: {place_name}")
                resolved = await resolve_place(
                    place_name=f"{place_name} {destination}",
                    location_bias=location_bias,
                )
                attr["resolved_place"] = resolved
                if resolved.get("resolved"):
                    attr["place_id"] = resolved.get("placeId", "")
                    attr["db_id"] = resolved.get("id", "")
                    attr["location"] = resolved.get("location", {})
                resolved_attractions.append(attr)

        attraction_result["attractions"] = resolved_attractions
        attraction_result["resolved_count"] = sum(1 for a in resolved_attractions if a.get("place_id"))

        # Build area distribution summary for downstream agents
        area_distribution = {}
        for attr in resolved_attractions:
            day = attr.get("suggested_day", 0)
            area = attr.get("area", "unknown")
            key = f"day_{day}"
            if key not in area_distribution:
                area_distribution[key] = {"area": area, "count": 0, "attractions": []}
            area_distribution[key]["count"] += 1
            area_distribution[key]["attractions"].append(attr.get("name", ""))
        attraction_result["area_distribution"] = area_distribution

        logger.info(f"   Suggested {len(attractions)} attractions, resolved {attraction_result['resolved_count']}")

    except Exception as e:
        logger.error(f"   ❌ Attraction Agent error: {e}", exc_info=True)
        attraction_result = {"error": str(e), "attractions": []}

    logger.info("🏛️ [ATTRACTION_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "attraction_agent",
        "current_tool": "place_resolver",
        "agent_outputs": {"attraction_agent": attraction_result},
        "messages": [AIMessage(content=f"[Attraction Agent] Found {len(attraction_result.get('attractions', []))} attractions for {destination}")],
    }


