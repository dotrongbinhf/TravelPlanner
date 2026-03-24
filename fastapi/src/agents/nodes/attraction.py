import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.tools.search_tools import tavily_search
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import settings

logger = logging.getLogger(__name__)

llm_attraction = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)

ATTRACTION_AGENT_SYSTEM = """You are the Attraction Agent for a travel planning system.

You suggest tourist attractions based on user preferences and trip context.

## Input
You receive two pieces of context from the Orchestrator:
1. **plan_context**: Shared trip info (departure, destination, dates, num_days, travelers, interest, pace, budget_level, currency, geographic_type, mobility_plan, local_transportation)
2. **attraction context**: Attraction-specific info (segments with segment_name/days/area_description, notes, user_attractions_preferences with interest/must_visit/to_avoid/notes)

## CRITICAL — How to use mobility_plan
The **mobility_plan** in plan_context tells you HOW the traveler arrives and departs. You MUST read it carefully to decide how much free time is available on each day:
- Adjust the number and timing of attractions per day accordingly.

## Process
1. Read both plan_context and attraction context carefully
2. Pay close attention to **mobility_plan** to understand arrival/departure timing and adjust Day 1 and last day attractions accordingly
3. Look at each **segment** — it tells you which days belong to which area
4. Read the **notes** field in attraction context — it contains critical info like "Day 1 is arrival day", "Day 3 is dedicated to Ba Vi", "Day 4 is departure day", etc.
5. Use your LLM knowledge to suggest attractions for EACH segment/day following the area assignments and themes
6. Use **tavily_search** ONLY when:
   - The user explicitly asks for new/trending/hot/recently-opened places
   - You feel your training data might not cover recent developments at the destination (e.g., newly opened museums, seasonal festivals, temporary exhibitions in 2026)
   - You need more options to better match unusual or specific user interests
7. Do NOT use tavily_search for well-known, established attractions
8. Return EXACT place names that are findable on Google Maps

## Tool: tavily_search (optional — for discovering new/trending places)
- query: Search text (e.g., "Top historical attractions in Hanoi", "Top hidden gems in Hanoi")
- max_results: default 5
- Use this ONLY when needed as described above

## Response Format
CRITICAL: If your next step is to use a tool, return your response to call the tool. If you don't need to use tools anymore, your response must be one and ONLY one valid JSON object. No text before or after. Just the raw JSON starting with { and ending with }.

EXAMPLE - FINAL OUTPUT STRUCTURE:
{
    "attractions": [
        {
            "name": "Hoan Kiem Lake (using exact name as Google Maps)",
            "suggested_duration_minutes": 60,
        },
        {
            "name": "Ngoc Son Temple (using exact name as Google Maps)",
            "suggested_duration_minutes": 30,
        }
    ]
}

## CRITICAL — About suggested_duration_minutes
**suggested_duration_minutes** is the ON-SITE VISIT TIME — the time the traveler actually spends AT the attraction exploring, viewing, experiencing it.
- It does NOT include travel time to/from the attraction. Travel time between attractions will be calculated separately by the Itinerary Agent later.
- Base your estimate on realistic visit duration for each specific attraction (e.g., a large national museum = 120-180 min, a small temple = 30-45 min, a scenic viewpoint = 20-30 min, a park = 60-120 min).
- Adjust based on the user's **pace**:
  - **relaxed**: Longer on-site time — travelers want to enjoy each place thoroughly (e.g., museum 180 min instead of 120)
  - **moderate**: Standard visit durations
  - **packed**: Shorter on-site time — travelers want to see more places quickly (e.g., museum 90 min instead of 120)

## CRITICAL — Understanding Segments
Each **segment** in the attraction context represents a MOVEMENT PLAN — it tells you WHERE the traveler will be on which days. How you interpret segments depends on the **geographic_type**:

### CENTRALIZED / CENTRALIZED_WITH_OUTLIER (city trip)
- Each segment defines an **area** to explore (e.g., "Central Hanoi", "Ba Vì excursion")
- Find attractions that are WITHIN or very NEAR that area
- City attractions are typically close together, so travelers can visit more places per day

### ROAD_TRIP
- Each segment represents a **route or leg** of the journey (e.g., "Hà Giang → Quản Bạ → Yên Minh")
- You MUST find attractions, scenic viewpoints, check-in spots, and interesting stops **ALONG the route** between the segment's origin and destination
- Include a mix of: major attractions worth a long stop, roadside scenic viewpoints for quick photo stops, local markets or villages worth a brief visit, natural landmarks along the road
- Road trip attractions should feel like a journey — the route itself is part of the experience

## Rules — How Many Attractions?
- Do NOT follow a fixed number. Decide based on:
  - **Available time**: How many hours does the traveler actually have on that day? (Consider mobility_plan for arrival/departure days)
  - **Pace**: relaxed travelers prefer fewer attractions with longer on-site time; packed travelers want more places with shorter visits
  - **Geographic type**: City trips allow more attractions per day (short commutes); road trips mean fewer major stops (long drives between them) but can include quick roadside stops
  - **Destination characteristics**: A day in a dense cultural district may have many walkable attractions; a day in a remote nature area may have only a few spread-out spots

## Rules — Content
- For CENTRALIZED segments: attractions must be IN or very NEAR the assigned area
- For ROAD_TRIP segments: attractions must be ALONG or NEAR the route described in the segment
- Use EXACT place names that exist on Google Maps
- Include must_visit places from user_attractions_preferences
- Exclude places listed in to_avoid
- Consider the travelers: children → kid-friendly places, elderly → accessible places
- Consider budget_level for paid attractions
- Every attraction MUST have a suggested_duration_minutes — this is ON-SITE time only, NOT including travel
"""

async def attraction_agent_node(state: GraphState) -> dict[str, Any]:
    """Attraction Agent — LLM-first suggestion with optional Tavily search. Runs in Phase 1."""
    logger.info("=" * 60)
    logger.info("🏛️ [ATTRACTION_AGENT] Node entered (Phase 1)")

    plan = state.get("orchestrator_plan", {})
    plan_context = plan.get("plan_context", {})
    attraction_ctx = plan.get("attraction", {})

    if not attraction_ctx:
        logger.info("   No attraction context → skip")
        return {
            "current_agent": "attraction_agent",
            "agent_outputs": {"attraction_agent": {"attractions": [], "skipped": True}},
            "messages": [AIMessage(content="[Attraction Agent] No attraction context provided")],
        }

    destination = plan_context.get("destination", "")
    attraction_result = {}

    try:
        human_content = f"""Plan context (shared trip info):
{json.dumps(plan_context, indent=2, ensure_ascii=False)}

Attraction-specific context:
{json.dumps(attraction_ctx, indent=2, ensure_ascii=False)}

Suggest tourist attractions based on this context. Use the plan_context for destination, dates, number of days, travelers, pace, budget, and especially the mobility_plan to understand arrival/departure timing. Use the attraction context for segments, area assignments, themes, and user preferences."""

        llm_messages = [
            SystemMessage(content=ATTRACTION_AGENT_SYSTEM),
            HumanMessage(content=human_content),
        ]

        result, tool_logs = await _run_agent_with_tools(
            llm=llm_attraction, messages=llm_messages,
            tools=[tavily_search], max_iterations=3,
            agent_name="ATTRACTION_AGENT",
        )
        attraction_result = _extract_json(result.content)
        attraction_result["tools"] = tool_logs

    except Exception as e:
        logger.error(f"   ❌ Attraction Agent error: {e}", exc_info=True)
        attraction_result = {"error": str(e), "attractions": []}

    logger.info("🏛️ [ATTRACTION_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "attraction_agent",
        "current_tool": "tavily_search",
        "agent_outputs": {"attraction_agent": attraction_result},
        "messages": [AIMessage(content=f"[Attraction Agent] Found {len(attraction_result.get('attractions', []))} attractions for {destination}")],
    }
