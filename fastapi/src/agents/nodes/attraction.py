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
        model=settings.MODEL_NAME,
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    # if USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model=settings.MODEL_NAME,
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_ATTRACTION or settings.GOOGLE_GEMINI_API_KEY,
        temperature=0.3,
        streaming=False,
    )
)

ATTRACTION_AGENT_SYSTEM = """You are the Attraction Agent for a travel planning system. You must use your thinking/reasoning ability to plan the attractions.

You suggest tourist attractions based on user preferences and trip context.

## Input
You receive:
1. **plan_context**: Shared trip info (departure, destination, dates, num_days, travelers, pace, budget_level, currency)
2. **mobility_plan**: Trip logistics — overview, segments with attraction_search_area and attraction_days
3. **task**: A concise description of what to search for — user interests, must_visit places, places to avoid, special notes

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
                    "notes": "Hồ Hoàn Kiếm, the historical heart of Hanoi, offers a peaceful escape with its iconic red bridge. Don't miss visiting Đền Ngọc Sơn, sitting elegantly on a small island, perfect for capturing the spirit of the city."
                },
                {
                    "name": "Lăng Chủ tịch Hồ Chí Minh",
                    "must_visit": true,
                    "estimated_entrance_fee": {"total": 0, "note": "Free admission"},
                    "includes": [
                        {"name": "Chùa Một Cột", "estimated_entrance_fee": {"total": 0, "note": "Free"}}
                    ],
                    "notes": "A monument of immense historical and cultural significance. Visitors can respectfully view the mausoleum, then take a short walk to see the architectural marvel of the One Pillar Pagoda nearby."
                },
                {
                    "name": "Nhà tù Hỏa Lò",
                    "must_visit": false,
                    "estimated_entrance_fee": {"total": 65000, "note": "30k × 2 adults + 5k × 1 child"},
                    "notes": "Known sarcastically as the 'Hanoi Hilton', this former prison provides a deeply moving look into Vietnam's colonial and wartime history through well-preserved artifacts and gripping exhibits."
                }
            ]
        },
        {
            "segment_name": "Ba Vi excursion",
            "attractions": [
                {
                    "name": "Vườn Quốc gia Ba Vì",
                    "must_visit": false,
                    "estimated_entrance_fee": {"total": 160000, "note": "60k × 2 adults + 40k child"},
                    "notes": "A stunning national park characterized by lush greenery, misty peaks, and fresh air. It's an ideal spot for hiking, exploring old French ruins, and enjoying a relaxing day in nature."
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

## Rules — How Many Attractions?
- Decide based on:
  - **Available time**: How many hours on each day? (Consider mobility_plan.overview for arrival/departure)
  - **Pace**: relaxed = fewer per day; packed = more per day
  - **Trip type**: City trips = more per day (short commutes); road trips = fewer major stops
- Over-provisioning: You MUST suggest about **20% MORE** attractions than what would fit in the schedule. This gives the Itinerary Agent flexibility to drop, swap, and optimize.

## Rules — Content
- Attractions must be IN or NEAR the segment's `attraction_search_area`
- Use EXACT place names that exist on Google Maps
- Include must_visit places from user_attractions_preferences — set must_visit=true. Others get must_visit=false.
- Exclude places listed in to_avoid
- Consider the travelers: children → kid-friendly, elderly → accessible
- Consider budget_level for paid attractions
- Every attraction MUST have a must_visit field (true or false)
- **Every attraction MUST have a `notes` field.** This field MUST be a highly engaging, well-written overview describing the attraction's significance, what to expect, and clearly mentioning any sub-attractions listed under `includes` (if any). Make it sound like a travel guidebook!
- Every attraction MUST have an estimated_entrance_fee: {"total": <number>, "note": "<explanation>"}. "total" is for ENTIRE group.
- Each "includes" item must also have its own estimated_entrance_fee.
- Use common pricing knowledge — children under ~6 free, under ~15 50% off. If free, total=0.
- Group attractions into segments matching the segment_name from mobility_plan.segments.
- COMBINE nested/adjacent attractions: When physically INSIDE or ADJACENT (e.g., Ngoc Son Temple inside Hoan Kiem Lake), COMBINE into one entry. List sub-attractions in "includes" as {"name": "...", "estimated_entrance_fee": {...}}. Add "notes" explaining the relationship.
- Do NOT suggest transport hubs (bus stations, train stations, airports) as attractions. These are handled separately by the Itinerary Agent.
- ONLY suggest real, specific places that EXIST on Google Maps with a searchable name. Do NOT suggest generic activities (e.g., "scenic drive along the road", "roadside photo stop", "enjoy the view"). Every attraction must be a concrete, named location.

## Rules — Segments
- If the mobility_plan has MULTIPLE segments, create one output segment per mobility_plan segment.
- If the mobility_plan has only ONE segment, OR if there is NO mobility_plan (standalone query), use a **SINGLE** segment with a general name (e.g., the destination name like "Hanoi" or "Bangkok").
- Do NOT artificially split a simple query into multiple segments. Only use multiple segments when the mobility_plan explicitly defines them.
"""

async def attraction_agent_node(state: GraphState) -> dict[str, Any]:
    """Attraction Agent — LLM-first suggestion with optional Tavily search. Unified pipeline/standalone."""
    logger.info("=" * 60)
    logger.info("🏛️ [ATTRACTION_AGENT] Node entered")

    plan = state.get("macro_plan", {})
    current_plan = state.get("current_plan", {})
    plan_context = current_plan.get("plan_context", {})
    mobility_plan = plan.get("mobility_plan", {})

    # Unified task request — from Orchestrator (pipeline) or Intent (standalone)
    agent_requests = plan.get("agent_requests", {})
    agent_request = agent_requests.get("attraction", "")

    if not agent_request:
        logger.info("   No agent_request for attraction → skip")
        return {
            "agent_outputs": {"attraction_agent": {"attractions": [], "skipped": True}},

        }

    is_pipeline = bool(plan.get("task_list"))
    logger.info(f"   Mode: {'PIPELINE' if is_pipeline else 'STANDALONE'}")

    destination = plan_context.get("destination", "")
    attraction_result = {}

    try:
        human_content = f"""Plan context:
{json.dumps(plan_context, indent=2, ensure_ascii=False)}

Mobility plan:
{json.dumps(mobility_plan, indent=2, ensure_ascii=False) if mobility_plan else "N/A"}

Task:
{agent_request}"""

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

    if "tools" in attraction_result:
        attraction_result.pop("tools", None)

    return {
        "agent_outputs": {"attraction_agent": attraction_result},

    }

