import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.tools.search_tools import tavily_search
from src.services.place_resolution_llm import resolve_all_attractions
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from src.config import settings

logger = logging.getLogger(__name__)

# USE_VERCEL_AI_GATEWAY = True

llm_attraction = (
    ChatOpenAI(
        model="google/gemini-2.5-flash",
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    # if USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview",
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_ATTRACTION,
        temperature=0.3,
        streaming=False,
    )
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
                    "other_name": "Lăng Bác",
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
                    "other_name": "Văn Miếu - Quốc Tử Giám",
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
                    "other_name": "Hanoi Hilton",
                    "suggested_duration_minutes": 90,
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 65000, "note": "30k × 2 adults + 5k × 1 child"},
                    "notes": "Historical site."
                },
                {
                    "name": "Old Quarter",
                    "other_name": "Phố cổ Hà Nội",
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 0, "note": "Free — public area"},
                    "notes": "Ideal for experiencing local culture, street food, and souvenir shopping."
                },
                {
                    "name": "Hanoi Opera House",
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 0, "note": "Free exterior visit"},
                    "notes": "Beautiful French colonial architecture, great for a photo stop."
                },
                {
                    "name": "St. Joseph's Cathedral",
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
1. **plan_context**: Shared trip info (departure, destination, dates, num_days, travelers, interest, pace, budget_level, currency, mobility_plan with overview/segments, local_transportation)
2. **attraction context**: user_attractions_preferences (interest/must_visit/to_avoid/notes)

## CRITICAL — How to use mobility_plan
The **mobility_plan** in plan_context tells you HOW the traveler arrives and departs. You MUST read it carefully to decide how much free time is available on each day:
- Adjust the number and timing of attractions per day accordingly.

## Process
1. Read plan_context carefully — especially **mobility_plan.overview** for arrival/departure timing
2. Read **mobility_plan.segments** — each segment has `attraction_search_area` and `attraction_days`
3. Use segments as SEARCH GUIDANCE: find attractions in each segment's geographic area
4. Note: `attraction_days` is a SOFT assignment — Itinerary Agent may flexibly schedule across segments
5. Use your LLM knowledge to suggest attractions for EACH segment following the area
6. Use **tavily_search** ONLY when:
   - The user explicitly asks for new/trending/hot/recently-opened places
   - You feel your training data might not cover recent developments at the destination
   - You need more options to better match unusual or specific user interests
7. Do NOT use tavily_search for well-known, established attractions
8. Return place names in the **local language of the destination** (based on the `language` field in plan_context). For example, if language is "vi" and destination is Hanoi, use "Hồ Hoàn Kiếm" instead of "Hoan Kiem Lake". This ensures accurate matching when resolving places on Google Maps.

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
            "attractions": [
                {
                    "name": "Hồ Hoàn Kiếm",
                    "must_visit": false,
                    "estimated_entrance_fee": {"total": 0, "note": "Free — public area"},
                    "includes": [
                        {"name": "Đền Ngọc Sơn", "estimated_entrance_fee": {"total": 60000, "note": "30k × 2 adults, free child"}}
                    ],
                    "notes": "Includes visit to Ngoc Son Temple located on the lake"
                },
                {
                    "name": "Lăng Chủ tịch Hồ Chí Minh",
                    "other_name": "Lăng Bác",
                    "must_visit": true,
                    "estimated_entrance_fee": {"total": 0, "note": "Free admission"},
                    "includes": [
                        {"name": "Chùa Một Cột", "estimated_entrance_fee": {"total": 0, "note": "Free"}}
                    ],
                    "notes": "Chùa Một Cột is within walking distance in the same complex"
                },
                {
                    "name": "Nhà tù Hỏa Lò",
                    "other_name": "Hanoi Hilton",
                    "must_visit": false,
                    "estimated_entrance_fee": {"total": 65000, "note": "30k × 2 adults + 5k × 1 child"}
                }
            ]
        },
        {
            "segment_name": "Ba Vi excursion",
            "attractions": [
                {
                    "name": "Vườn Quốc gia Ba Vì",
                    "must_visit": false,
                    "estimated_entrance_fee": {"total": 160000, "note": "60k × 2 adults + 40k child"}
                }
            ]
        }
    ]
}

## CRITICAL — Understanding Segments
Each **segment** in mobility_plan.segments represents a GEOGRAPHIC AREA for search. Use the `attraction_search_area` field to know WHERE to look for attractions.

- For city trips: segments define areas to explore (e.g., "Central Hanoi", "Ba Vì excursion")
- For road trips: segments represent route legs (e.g., "Hà Giang → Quản Bạ → Yên Minh")
  - Find attractions, scenic viewpoints, check-in spots ALONG the route
  - Include a mix: major stops, scenic viewpoints, local markets, natural landmarks

## Rules — Naming
- The `name` field contains ONLY the place name — no alternative names, no parenthetical info.
- If a place has a well-known alternative name that locals commonly use (e.g., "Lăng Bác" for "Lăng Chủ tịch Hồ Chí Minh", "Hanoi Hilton" for "Nhà tù Hỏa Lò"), add it as `other_name`.
- `other_name` is optional — omit it if the place doesn't have a widely-known alternative name.
- Well-known, unambiguous places (e.g., "Hồ Hoàn Kiếm", "Hà Nội Opera House") do NOT need an other_name.

## Rules — How Many Attractions?
- Decide based on:
  - **Available time**: How many hours on each day? (Consider mobility_plan.overview for arrival/departure)
  - **Pace**: relaxed = fewer per day; packed = more per day
  - **Trip type**: City trips = more per day (short commutes); road trips = fewer major stops
- Over-provisioning: You MUST suggest **20-30% MORE** attractions than what would fit in the schedule. This gives the Itinerary Agent flexibility to drop, swap, and optimize.

## Rules — Content
- Attractions must be IN or NEAR the segment's `attraction_search_area`
- Use EXACT place names that exist on Google Maps
- Include must_visit places from user_attractions_preferences — set must_visit=true. Others get must_visit=false.
- Exclude places listed in to_avoid
- Consider the travelers: children → kid-friendly, elderly → accessible
- Consider budget_level for paid attractions
- Every attraction MUST have a must_visit field (true or false)
- Every attraction MUST have an estimated_entrance_fee: {"total": <number>, "note": "<explanation>"}. "total" is for ENTIRE group.
- Each "includes" item must also have its own estimated_entrance_fee.
- Use common pricing knowledge — children under ~6 free, under ~15 50% off. If free, total=0.
- Group attractions into segments matching the segment_name from mobility_plan.segments.
- COMBINE nested/adjacent attractions: When physically INSIDE or ADJACENT (e.g., Ngoc Son Temple inside Hoan Kiem Lake), COMBINE into one entry. List sub-attractions in "includes" as {"name": "...", "estimated_entrance_fee": {...}}. Add "notes" explaining the relationship.
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

    # --- Phase 3: Filter out unresolved attractions (no placeId) ---
    # Only resolved attractions are passed to Itinerary Agent
    total_before_filter = sum(
        len(seg.get("attractions", []))
        for seg in attraction_result.get("segments", [])
    )
    for seg in attraction_result.get("segments", []):
        unresolved = [a.get("name", "?") for a in seg.get("attractions", []) if not a.get("placeId")]
        if unresolved:
            logger.warning(f"🏛️ [ATTRACTION_AGENT] Filtering {len(unresolved)} unresolved from '{seg.get('segment_name', '?')}': {unresolved}")
        seg["attractions"] = [a for a in seg.get("attractions", []) if a.get("placeId")]

    total_attractions = sum(
        len(seg.get("attractions", []))
        for seg in attraction_result.get("segments", [])
    )
    filtered_count = total_before_filter - total_attractions
    logger.info(f"🏛️ [ATTRACTION_AGENT] Node completed: {total_attractions} resolved, {filtered_count} filtered out")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"attraction_agent": attraction_result},
        "messages": [AIMessage(content=f"[Attraction Agent] Found {total_attractions} resolved attractions for {destination} ({filtered_count} filtered)")],
    }

