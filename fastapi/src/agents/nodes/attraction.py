import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.tools.search_tools import tavily_search
from src.services.place_resolution_llm import resolve_all_attractions
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import settings

logger = logging.getLogger(__name__)

llm_attraction = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)

ATTRACTION_AGENT_MOCK = {
    "segments": [
        {
            "segment_name": "Central Hanoi",
            "days": [0, 1, 2, 3],
            "attractions": [
                {
                    "name": "Hoan Kiem Lake",
                    "suggested_duration_minutes": 90,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 0, "note": "Free — public area"},
                    "includes": [
                        {"name": "Ngoc Son Temple", "estimated_entrance_fee": {"total": 60000, "note": "30k × 2 adults, free child under 15"}},
                        {"name": "The Huc Bridge", "estimated_entrance_fee": {"total": 0, "note": "Free — included with temple ticket"}}
                    ],
                    "notes": "Includes the iconic red bridge and the temple located on the islet within the lake."
                },
                {
                    "name": "Ho Chi Minh Mausoleum",
                    "suggested_duration_minutes": 120,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 0, "note": "Free admission"},
                    "includes": [
                        {"name": "One Pillar Pagoda", "estimated_entrance_fee": {"total": 0, "note": "Free"}},
                        {"name": "Ho Chi Minh Museum", "estimated_entrance_fee": {"total": 80000, "note": "40k × 2 adults, free child"}},
                        {"name": "Presidential Palace Historical Site", "estimated_entrance_fee": {"total": 100000, "note": "40k × 2 adults + 20k child"}}
                    ],
                    "notes": "A comprehensive complex; requires significant walking. Note: Mausoleum has specific morning hours."
                },
                {
                    "name": "Temple of Literature",
                    "suggested_duration_minutes": 90,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 75000, "note": "30k × 2 adults + 15k × 1 child (50% under 15)"},
                    "notes": "Vietnam's first university, excellent example of traditional architecture."
                },
                {
                    "name": "Thang Long Imperial Citadel",
                    "suggested_duration_minutes": 120,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 75000, "note": "30k × 2 adults + 15k × 1 child"},
                    "notes": "UNESCO World Heritage site with deep historical significance."
                },
                {
                    "name": "Vietnam Museum of Ethnology",
                    "suggested_duration_minutes": 150,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 100000, "note": "40k × 2 adults + 20k × 1 child"},
                    "notes": "Highly engaging for children and adults, featuring outdoor traditional houses."
                },
                {
                    "name": "Hoa Lo Prison Relic",
                    "suggested_duration_minutes": 90,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 65000, "note": "30k × 2 adults + 5k × 1 child"},
                    "notes": "Historical site."
                },
                {
                    "name": "Old Quarter",
                    "suggested_duration_minutes": 120,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 0, "note": "Free — public area"},
                    "notes": "Ideal for experiencing local culture, street food, and souvenir shopping."
                },
                {
                    "name": "Hanoi Opera House",
                    "suggested_duration_minutes": 45,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 0, "note": "Free exterior visit"},
                    "notes": "Beautiful French colonial architecture, great for a photo stop."
                },
                {
                    "name": "St. Joseph's Cathedral",
                    "suggested_duration_minutes": 30,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 0, "note": "Free admission"},
                    "notes": "Neo-Gothic cathedral in the heart of the city."
                }
            ]
        }
    ]
}

ATTRACTION_AGENT_SYSTEM = """You are the Attraction Agent for a travel planning system. You must use your thinking/reasoning ability to plan the attractions.

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
8. Return place names in the **local language of the destination** (based on the `language` field in plan_context). For example, if language is "vi" and destination is Hanoi, use "Hồ Hoàn Kiếm" instead of "Hoan Kiem Lake", "Văn Miếu - Quốc Tử Giám" instead of "Temple of Literature". This ensures accurate matching when resolving places on Google Maps.

## Tool: tavily_search (optional — for discovering new/trending places)
- query: Search text (e.g., "Top historical attractions in Hanoi", "Top hidden gems in Hanoi")
- max_results: default 5
- Use this ONLY when needed as described above

## Response Format
CRITICAL: If your next step is to use a tool, return your response to call the tool. If you don't need to use tools anymore, your response must be one and ONLY one valid JSON object. No text before or after. Just the raw JSON starting with { and ending with }.

EXAMPLE - FINAL OUTPUT STRUCTURE:
{
    "segments": [
        {
            "segment_name": "Central Hanoi",
            "days": [0, 1, 3],
            "attractions": [
                {
                    "name": "Hồ Hoàn Kiếm",
                    "suggested_duration_minutes": 90,
                    "must_visit": false,
                    "estimated_entrance_fee": {"total": 0, "note": "Free — public area"},
                    "includes": [
                        {"name": "Đền Ngọc Sơn", "estimated_entrance_fee": {"total": 60000, "note": "30k × 2 adults, free child"}}
                    ],
                    "notes": "Includes visit to Ngoc Son Temple located on the lake"
                },
                {
                    "name": "Lăng Chủ tịch Hồ Chí Minh",
                    "suggested_duration_minutes": 120,
                    "must_visit": true,
                    "estimated_entrance_fee": {"total": 0, "note": "Free admission"},
                    "includes": [
                        {"name": "Chùa Một Cột", "estimated_entrance_fee": {"total": 0, "note": "Free"}}
                    ],
                    "notes": "Chùa Một Cột is within walking distance in the same complex"
                }
            ]
        },
        {
            "segment_name": "Ba Vi excursion",
            "days": [2],
            "attractions": [
                {
                    "name": "Vườn Quốc gia Ba Vì",
                    "suggested_duration_minutes": 180,
                    "must_visit": false,
                    "estimated_entrance_fee": {"total": 160000, "note": "60k × 2 adults + 40k child"}
                }
            ]
        }
    ]
}

## CRITICAL — About suggested_duration_minutes
**suggested_duration_minutes** is the ON-SITE VISIT TIME — the time the traveler actually spends AT the attraction exploring, viewing, experiencing it.
- It does NOT include travel time to/from the attraction. Travel time between attractions will be calculated separately by the Itinerary Agent later.
- Base your estimate on realistic visit duration for each specific attraction.
- Adjust based on the user's **pace**:
  - **relaxed**: Longer on-site time — travelers want to enjoy each place thoroughly
  - **moderate**: Standard visit durations
  - **packed**: Shorter on-site time — travelers want to see more places quickly

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
- Decide based on:
  - **Available time**: How many hours does the traveler actually have on that day? (Consider mobility_plan for arrival/departure days)
  - **Pace**: relaxed travelers prefer fewer attractions with longer on-site time; packed travelers want more places with shorter visits
  - **Geographic type**: City trips allow more attractions per day (short commutes); road trips mean fewer major stops (long drives between them) but can include quick roadside stops
  - **Destination characteristics**: A day in a dense cultural district may have many walkable attractions; a day in a remote nature area may have only a few spread-out spots
  - You MUST suggest MORE attractions than needed for the available time. Extra non-must-visit attractions serve as alternatives for the user and allow the Itinerary Agent flexibility to fill gaps or replace dropped places.


## Rules — Content
- For CENTRALIZED segments: attractions must be IN or NEAR the assigned area
- For ROAD_TRIP segments: attractions must be ALONG or NEAR the route described in the segment
- Use EXACT place names that exist on Google Maps
- Include must_visit places from user_attractions_preferences — set must_visit=true for those. All other attractions you suggest on your own get must_visit=false.
- You MUST suggest MORE attractions than needed for the available time. Extra non-must-visit attractions serve as alternatives for the user and allow the Itinerary Agent flexibility to fill gaps or replace dropped places.
- Exclude places listed in to_avoid
- Consider the travelers: children → kid-friendly places, elderly → accessible places
- Consider budget_level for paid attractions
- Every attraction MUST have a suggested_duration_minutes — this is ON-SITE time only, NOT including travel
- Every attraction MUST have a must_visit field (true or false)
- Every attraction MUST have an estimated_entrance_fee: {"total": <number>, "note": "<explanation>"}. "total" is the fee for the main attraction only, for the ENTIRE group.
- Each item in "includes" must also have its own estimated_entrance_fee. This allows the Itinerary Agent to include/exclude sub-attractions and adjust the total cost accordingly.
- Use your knowledge of common pricing — children under ~6 usually free, under ~15 usually 50% off. If free, set total=0.
- Group your attractions into segments that match EXACTLY the segment_name values from the attraction context. Each segment must include its segment_name and days array (copied from the input). This tells the Itinerary Agent which days each group of attractions can be scheduled on.
- COMBINE nested/adjacent attractions: When attractions are physically INSIDE or immediately ADJACENT to each other (e.g., Ngoc Son Temple inside Hoan Kiem Lake, One Pillar Pagoda next to Ho Chi Minh Mausoleum complex), COMBINE them into a SINGLE entry under the main attraction name. Set suggested_duration_minutes to cover ALL included visits. List sub-attractions in "includes" as objects with {"name": "...", "estimated_entrance_fee": {...}}. Add a "notes" field explaining the relationship. Do NOT list them as separate entries.
- Do NOT suggest transport hubs (bus stations, train stations, airports) as attractions. These are handled separately by the Itinerary Agent.
- ONLY suggest real, specific places that EXIST on Google Maps with a searchable name. Do NOT suggest generic activities (e.g., "scenic drive along the road", "roadside photo stop", "enjoy the view"). Every attraction must be a concrete, named location.
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

        # MOCK - HN
        # attraction_result = _extract_json(ATTRACTION_AGENT_MOCK)

    except Exception as e:
        logger.error(f"   ❌ Attraction Agent error: {e}", exc_info=True)
        attraction_result = {"error": str(e), "segments": []}

    # --- Phase 2: Resolve attraction names to verified placeIds ---
    if attraction_result.get("segments") and not attraction_result.get("error"):
        try:
            logger.info("🏛️ [ATTRACTION_AGENT] Phase 2: Resolving places with LLM verification...")
            attraction_result = await resolve_all_attractions(
                attraction_result, destination=destination,
            )
        except Exception as e:
            logger.error(f"   ❌ Place resolution error: {e}", exc_info=True)
            # Continue with unresolved data — itinerary builder will try to resolve

    # Count total attractions across all segments
    total_attractions = sum(
        len(seg.get("attractions", []))
        for seg in attraction_result.get("segments", [])
    )
    resolved_count = sum(
        1 for seg in attraction_result.get("segments", [])
        for attr in seg.get("attractions", [])
        if attr.get("placeId")
    )
    logger.info(f"🏛️ [ATTRACTION_AGENT] Node completed: {resolved_count}/{total_attractions} resolved")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"attraction_agent": attraction_result},
        "messages": [AIMessage(content=f"[Attraction Agent] Found {total_attractions} attractions for {destination} ({resolved_count} resolved)")],
    }

