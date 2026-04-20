import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _get_latest_user_message, _run_agent_with_tools
from src.tools.search_tools import tavily_search
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from src.config import settings
from src.services.place_resolution_llm import resolve_all_attractions

logger = logging.getLogger(__name__)

# USE_VERCEL_AI_GATEWAY = True

llm_orchestrator = (
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
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_ORCHESTRATOR or settings.GOOGLE_GEMINI_API_KEY,
        temperature=0.3,
        streaming=False,
    )
)

ORCHESTRATOR_SYSTEM = """You are the Macro Planning Agent for a multi-agent travel planning system.

Your ONLY job is to:
1. Create a DETAILED mobility plan that covers the entire trip
2. Create a structured plan with SPECIFIC CONTEXT for each specialist agent

Note: Intent detection and clarification are handled BEFORE you. You will ONLY be called when the user wants to create or modify a plan. The user's request has already been validated to have sufficient information.

## Web Search
You have access to the `tavily_search` tool. BEFORE building the `mobility_plan` for unfamiliar destinations, complex multi-region trips, or specific multi-day routes (like "x days Ha Giang loop"), use the `tavily_search` tool to gather high-level itinerary and routing ideas. Use this research ONLY to inform the `mobility_plan.segments` structure (which areas on which days) and logistics, not for fine-grained daily scheduling.

## Response Format

CRITICAL: Your response must be one and ONLY one valid JSON object. No text before or after.

```json
{
  "mobility_plan": {
    "overview": "[DETAILED high-level plan — see rules below]",
    "departure_logistics": {
      "mode": "coach",
      "hub_name": "Ha Giang Bus Station",
      "start_time": "22:00 -1",
      "arrival_time": "05:00",
      "estimated_cost": 500000,
      "estimated_cost_note": "250,000 VND/person × 2 people",
      "note": "Overnight coach from Hanoi 22:00, arrives HG 05:00. Rest until 07:00."
    },
    "return_logistics": {
      "mode": "coach",
      "hub_name": "Ha Giang Bus Station",
      "start_time": "14:00",
      "arrival_time": "21:00",
      "estimated_cost": 500000,
      "estimated_cost_note": "250,000 VND/person × 2 people",
      "note": "Coach back to Hanoi, departs 14:00, arrives 21:00."
    },
    "segments": [
      {
        "segment_id": 0,
        "segment_name": "Ha Giang → Quan Ba → Yen Minh",
        "attraction_days": [0],
        "hotel_nights": [0],
        "hotel_search_area": "Yen Minh town center",
        "attraction_search_area": "Along the route Ha Giang city → Quan Ba → Yen Minh"
      }
    ]
  },

  "context_fill": {
    "pace": "moderate",
    "budget_level": "moderate",
    "currency": "VND",
    "language": "vi",
    "local_transportation": "car"
  },

  "task_list": ["attraction", "hotel", "flight"],

  "agent_requests": {
    "attraction": "Search tourist attractions. User interests: history, cultural. Must visit: Ho Chi Minh Mausoleum.",
    "flight": "Search flights. Type: one_way, directions: both. Prefer arrive 8:00 AM - 10:00 AM at destination. Prefer depart 3:00 PM - 7:00 PM from destination. 0 infants in seat, 0 on lap. Economy class.",
    "hotel": "Search hotels. children_ages: 8. User prefers near the Old Quarter area."
  }
}
```

## agent_requests — CRITICAL
The `agent_requests` dict describes the TASK for each specialist agent.
Each agent also receives `plan_context` and `mobility_plan` separately — do NOT repeat info already in those (departure, destination, dates, num_days, adults, children, budget_level, currency, pace, etc.).

Only include information SPECIFIC to the task that is NOT already available in plan_context.
If the user did NOT mention a specific preference, do NOT invent one — the agent will use reasonable defaults.

### For attraction:
- Start with "Search tourist attractions."
- User's interests, must_visit places, places to avoid (ONLY if user mentioned them, no auto-generated their places to visit/avoid)
- Any special user notes about attractions

### For flight:
- Start with "Search flights."
- Type: one_way or round_trip. Directions: both, outbound_only, return_only. Default to type "one_way", directions "both" for plan_creation.
- Preferred time windows (outbound_times, return_times) — from user, or generate REASONABLE defaults based on trip context. Format: "Prefer arrive X - Y at destination" / "Prefer depart X - Y from destination".
- infants_in_seat and infants_on_lap (REQUIRED when infants > 0, sum = infants). Include even when 0.
- Travel class (default economy)
- Any user notes about flight (e.g., "direct flights only", "prefer VietJet")

### For hotel:
- Start with "Search hotels."
- children_ages: comma-separated ages for ALL children + infants (REQUIRED when children + infants > 0)
- Price range per night ONLY if user specified (e.g., "800,000-1,500,000 VND/night")
- Any user preferences/notes about hotel (e.g., "near the beach", "prefer 4-star")

### For restaurant:
- Start with "Search restaurants."
- Cuisine preferences and dietary restrictions (ONLY if user mentioned them)
- Any special notes about food

## task_list Rules
- MUST include "attraction"
- ONLY include "flight", "hotel", and "restaurant" IF the intent is `full_plan` (or if explicitly requested in `modify_plan`) AND they are applicable:
  - Include "flight" ONLY if intent is full_plan AND departure_logistics.mode is "flight" AND user needs flight.
  - Include "hotel" ONLY if intent is full_plan AND user needs hotel.
  - Include "restaurant" ONLY if intent is full_plan AND user needs restaurant.
- If intent is `draft_plan`: `task_list` MUST ONLY contain `["attraction"]`.
- Omit agents that are not needed

## Mobility Plan — CRITICAL

### overview
MUST be a DETAILED high-level plan covering the ENTIRE trip, written as a comprehensive paragraph. Include:
- How travelers get from departure → destination (mode, estimated time, cost)
- What happens upon arrival (rest? explore? check-in?)
- Daily rhythm per day/segment (full day exploration, road trip route, day trip details)
- Return journey (checkout, last activities, departure timing)
- Factor in: departure mode (from departure_logistics.mode), pace, children/infants, local transportation

### departure_logistics & return_logistics

**When mode is "flight" (FULL plan — Flight Agent will handle):**
```json
"departure_logistics": { "mode": "flight" },
"return_logistics": { "mode": "flight" }
```
Flight Agent provides ALL flight data. No other fields needed.

**When mode is "flight" (DRAFT plan — YOU estimate):**
When intent is "draft_plan", you MUST estimate flight timing yourself:
```json
"departure_logistics": {
  "mode": "flight",
  "estimated": true,
  "hub_name": "Da Nang Airport (DAD)",
  "start_time": "07:00",
  "arrival_time": "08:20",
  "note": "Estimated flight HCM → Da Nang, ~1h20"
},
"return_logistics": {
  "mode": "flight",
  "estimated": true,
  "hub_name": "Da Nang Airport (DAD)",
  "start_time": "19:00",
  "arrival_time": "20:20",
  "note": "Estimated flight Da Nang → HCM, ~1h20"
}
```
- `hub_name`: The airport name at the DESTINATION (use your knowledge of Vietnamese/international airports)
- `start_time`: Estimated departure time from origin
- `arrival_time`: Estimated arrival time at destination
- `estimated: true`: Flag so downstream agents know this is an estimate, NOT real flight data

**When mode is "coach", "train":**
```json
"departure_logistics": {
  "mode": "coach",
  "hub_name": "Ha Giang Bus Station",
  "start_time": "22:00 -1",
  "arrival_time": "05:00",
  "estimated_cost": 500000,
  "estimated_cost_note":  "250,000 VND/person × 2 people",
  "note": "Context about arrival"
}
```
hub_name = the DESTINATION-SIDE hub (where traveler arrives/departs at destination).
`start_time`: Time of departure from origin (append " -1" if it departs the previous day).
`arrival_time`: Time of arrival at destination hub.
You MUST provide estimated_cost.
estimated_cost MUST be a numeric total (integer) for ALL travelers, with estimated_cost_note explaining the breakdown (e.g., "250,000 VND/person × 2").

**When mode is "car", "motorbike":**
```json
"departure_logistics": {
  "mode": "car",
  "hub_name": null,
  "start_time": "06:30",
  "arrival_time": "08:00",
  "estimated_cost": 150000,
  "estimated_cost_note": "tolls + fuel ~150,000 VND",
  "note": "Self-drive from Bac Ninh"
}
```
hub_name is null for self-drive (no fixed hub). Itinerary starts at first attraction or hotel.

**When local (departure == destination):**
```json
"departure_logistics": null,
"return_logistics": null
```

### segments

Each segment defines a geographic area for agent search:
- `segment_id`: numeric, 0-indexed (0, 1, 2, ...)
- `segment_name`: descriptive name
- `attraction_days`: 0-indexed day numbers for attraction search (SOFT guidance — Itinerary Agent may flexibly assign across segments)
- `hotel_nights`: 0-indexed night numbers (HARD constraint — Hotel Agent searches by specific dates)
- `hotel_search_area`: where to search for hotel (null if no overnight in this segment)
- `attraction_search_area`: geographic area for attraction search
- `notes`: optional context

Day trip example (Ba Vì in day, return to Hanoi):
- Ba Vì segment: `hotel_nights: []` (no overnight), `attraction_days: [2]`
- Hanoi segment: `hotel_nights: [0, 1, 2]` (stays all nights), `attraction_days: [0, 1, 3]`

**IMPORTANT**: Only create multi-region segments (like day trips to nearby areas) when:
- User explicitly requests nearby destinations (e.g., "I also want to visit Ba Vì", "include Hải Phòng")
- User hints at wanting more variety (e.g., "what else can we do around here?")
Do NOT proactively suggest day trips to other regions unless the user asks.

## Rules

- CRITICAL: Response MUST be one valid JSON object. No text before or after.
- DO NOT generate plan_context fields (departure, destination, dates, travelers etc.) — those are already set by the Intent Agent.
  You only generate: `mobility_plan`, `context_fill`, `task_list`, and `agent_requests`.
- `context_fill` is for fields the user hasn't explicitly mentioned. Fill sensible defaults:
   - `pace`: default "moderate"
   - `budget_level`: default "moderate"
   - `local_transportation`: choose the most reasonable mode
   - `currency`: infer from user's message language
   - `language`: infer from user's message language
- Only set null for fields that are irrelevant.

- Attraction preferences MUST NOT include food/cuisine-related interests.
"""

async def _resolve_non_flight_hubs(plan: dict, state_plan_context: dict = None) -> dict:
    """Resolve non-flight transport hubs using LLM-verified pattern.

    When mode is coach/train, hub_name is an LLM-generated name (e.g., "Bến xe Hà Giang").
    We resolve it to a real placeId using the same LLM-verified approach as Attraction Agent.

    Modifies plan in-place, adding hub_placeId to logistics.
    """
    mobility_plan = plan.get("mobility_plan") or {}
    dep_log = mobility_plan.get("departure_logistics") or {}
    ret_log = mobility_plan.get("return_logistics") or {}
    mode = dep_log.get("mode", "")

    # Only resolve for non-flight modes with hub_name
    if mode in ("flight", "") or not mode:
        return plan

    destination = state_plan_context.get("destination", "") if state_plan_context else ""
    hubs_to_resolve = []

    dep_hub = dep_log.get("hub_name")
    ret_hub = ret_log.get("hub_name")

    if dep_hub:
        hubs_to_resolve.append({"name": dep_hub, "target": "departure"})
    if ret_hub and ret_hub != dep_hub:
        hubs_to_resolve.append({"name": ret_hub, "target": "return"})

    if not hubs_to_resolve:
        return plan

    logger.info(f"🔍 [ORCHESTRATOR] Resolving {len(hubs_to_resolve)} transport hub(s)...")

    # Build a minimal "attraction-like" structure for resolve_all_attractions
    fake_attraction_result = {
        "segments": [{
            "segment_name": "transport_hubs",
            "attractions": [{"name": h["name"]} for h in hubs_to_resolve],
        }]
    }

    resolved = await resolve_all_attractions(
        fake_attraction_result,
        destination=destination,
    )

    # Extract resolved placeIds
    resolved_attrs = resolved.get("segments", [{}])[0].get("attractions", [])

    for hub_info, resolved_attr in zip(hubs_to_resolve, resolved_attrs):
        place_id = resolved_attr.get("placeId")
        resolved_name = resolved_attr.get("name", hub_info["name"])

        if place_id:
            logger.info(f"   ✅ Hub '{hub_info['name']}' → placeId={place_id}, name='{resolved_name}'")
            if hub_info["target"] == "departure":
                dep_log["hub_placeId"] = place_id
                dep_log["hub_name"] = resolved_name
            elif hub_info["target"] == "return":
                ret_log["hub_placeId"] = place_id
                ret_log["hub_name"] = resolved_name
            # If return hub same as departure, sync both
            if ret_hub == dep_hub and hub_info["target"] == "departure":
                ret_log["hub_placeId"] = place_id
                ret_log["hub_name"] = resolved_name
        else:
            logger.warning(f"   ⚠️ Could not resolve hub '{hub_info['name']}'")

    return plan


async def orchestrator_nonVRP_node(state: GraphState) -> dict[str, Any]:
    """Orchestrator (Macro Planning) — Parses user request into structured per-agent JSON.
    Phase 1: LLM generates plan with mobility_plan.
    Phase 2: Resolve non-flight transport hubs (LLM-verified).

    Reads intent from Intent Agent to determine draft vs full mode."""
    logger.info("=" * 60)
    logger.info("🧠 [ORCHESTRATOR_nonVRP] Node entered")

    user_message = _get_latest_user_message(state)
    user_context = state.get("user_context", {})
    routed_intent = state.get("routed_intent", "draft_plan")

    logger.info(f"   User message: {user_message[:100]}")
    logger.info(f"   Routed intent from Intent Agent: {routed_intent}")

    try:
        # Build LLM messages with draft/full/modify hint
        system_content = ORCHESTRATOR_SYSTEM
        if routed_intent == "draft_plan":
            system_content += """

## DRAFT MODE ACTIVE
You are creating a DRAFT plan. For departure_logistics/return_logistics:
- If mode is "flight": you MUST provide estimated timing (hub_name, start_time, arrival_time, estimated: true).
  Flight Agent will NOT run — your estimates will be used directly.
- For hotel: provide hotel_search_area in segments as usual (Hotel Agent will NOT run).
- For tasks: you MUST still provide attraction and restaurant context.
  Flight and hotel task sections can be null (agents won't run).
"""
        elif routed_intent == "modify_plan":
            system_content += """

## MODIFY MODE ACTIVE
You are MODIFYING an existing plan. The existing plan context is provided below.
- Incorporate the user's requested changes into the plan.
- Keep unchanged sections as-is — only modify what the user asked to change.
- If the user changed dates/travelers, update ALL affected sections accordingly.
- Re-generate the full plan structure with the modifications applied.
"""

        # ── Context from Intent Agent (replaces conversation history) ──
        current_plan = state.get("current_plan", {})
        existing_plan_ctx = current_plan.get("plan_context", {})
        last_intent = current_plan.get("last_intent_info", state.get("last_intent", {}))
        user_request_rewrite = last_intent.get("user_request_rewrite", "")
        
        # Build prompt messages
        llm_messages = [SystemMessage(content=system_content)]
        if user_request_rewrite:
            llm_messages.append(HumanMessage(
                content=f"Current user request: {user_request_rewrite}"
            ))

        # Inject existing plan context if available
        if existing_plan_ctx:
            llm_messages.append(SystemMessage(
                content=f"Existing trip context (from previous turns):\n{json.dumps(existing_plan_ctx, indent=2, ensure_ascii=False)}"
            ))

        # Inject constraint overrides (user-provided flight/hotel times)
        constraint_overrides = state.get("constraint_overrides", {})
        if constraint_overrides:
            override_msg = (
                "## User-Provided Time Constraints (MUST USE)\n"
                "The user has explicitly specified these times. You MUST use them:\n"
                f"{json.dumps(constraint_overrides, indent=2, ensure_ascii=False)}\n\n"
                "Rules:\n"
                "- If outbound_departure_time/outbound_arrival_time provided → use in departure_logistics (start_time/arrival_time)\n"
                "- If return_departure_time provided → use in return_logistics (start_time) and base deadline on it\n"
                "- If hotels overrides provided → use the specified check_in_time/check_out_time for those nights\n"
                "- For flight task: use these times in outbound_times/return_times preferences\n"
            )
            llm_messages.append(SystemMessage(content=override_msg))
            logger.info(f"   🔧 Injected constraint_overrides into Orchestrator: {constraint_overrides}")

        # Only latest user message (not full history)
        llm_messages.append(HumanMessage(content=user_message))

        # Phase 1: LLM generates plan, potentially using tavily_search
        result, tool_logs = await _run_agent_with_tools(
            llm=llm_orchestrator,
            messages=llm_messages,
            tools=[tavily_search],
            max_iterations=4,
            agent_name="ORCHESTRATOR_nonVRP"
        )
        
        output = _extract_json(result.content)

        # Extract mobility_plan, context_fill, and agent_requests from LLM output
        mobility_plan = output.get("mobility_plan", {})
        context_fill = output.get("context_fill", {})
        agent_requests = output.get("agent_requests", {}) or {}
        task_list = output.get("task_list", []) or []

        # Fallback: if LLM didn't output task_list, infer from agent_requests keys
        if not task_list and agent_requests:
            task_list = list(agent_requests.keys())

        # Merge context_fill into current_plan.plan_context (only fill missing fields)
        current_plan = state.get("current_plan", {})
        plan_ctx = current_plan.get("plan_context", {})
        for key, value in context_fill.items():
            if value is not None and not plan_ctx.get(key):
                plan_ctx[key] = value
        current_plan["plan_context"] = plan_ctx

        logger.info(f"   Routed intent: {routed_intent}, Tasks: {task_list}")
        logger.info(f"   Agent requests: {list(agent_requests.keys())}")

        macro_plan = {
            "task_list": task_list,
            "mobility_plan": mobility_plan,
            "agent_requests": agent_requests,
        }

        # Phase 2: Resolve non-flight transport hubs (skip for draft estimated flights)
        dep_log = (mobility_plan.get("departure_logistics") or {})
        if not dep_log.get("estimated"):
            macro_plan = await _resolve_non_flight_hubs(macro_plan, plan_ctx)

        logger.info(f"   🚀 Plan created: {task_list}")

        return {
            "pending_tasks": task_list,
            "completed_tasks": [],
            "user_context": user_context,
            "macro_plan": macro_plan,
            "current_plan": current_plan,
            "agent_outputs": {"orchestrator": {"intent": routed_intent, "tasks": task_list}},
            "messages": [AIMessage(content=f"[Orchestrator] Plan created: {', '.join(task_list)} agents will execute...")],
        }

    except Exception as e:
        logger.error(f"   ❌ Orchestrator error: {e}", exc_info=True)
        current_plan = state.get("current_plan", {})
        plan_context = current_plan.get("plan_context", {})
        language = plan_context.get("language", "en")
        fallback = "Đã xảy ra lỗi khi phân tích chuyến đi. Vui lòng thử lại." if language == "vi" else "I'm sorry, I encountered an error. Could you try rephrasing your request?"
        return {
            "pending_tasks": [],
            "completed_tasks": [],
            "user_context": user_context,
            "macro_plan": {"task_list": []},
            "agent_outputs": {"orchestrator": {"error": str(e)}},
            "messages": [AIMessage(content=fallback)],
            "final_response": fallback,
        }

