import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _get_latest_user_message, _get_conversation_context, _run_agent_with_tools
from src.tools.search_tools import tavily_search
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from src.config import settings
from src.services.place_resolution_llm import resolve_all_attractions

logger = logging.getLogger(__name__)

# USE_VERCEL_AI_GATEWAY = True

llm_orchestrator = (
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
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_ORCHESTRATOR,
        temperature=0.3,
        streaming=False,
    )
)

ORCHESTRATOR_SYSTEM = """You are the Orchestrator Agent for a multi-agent travel planning system.

Your PRIMARY job is to:
1. Understand the user's travel request
2. Ask clarification if critical info is missing
3. Create a DETAILED mobility plan that covers the entire trip
4. Create a structured plan with SPECIFIC CONTEXT for each specialist agent

## Web Search
You have access to the `tavily_search` tool. BEFORE building the `mobility_plan` for unfamiliar destinations, complex multi-region trips, or specific multi-day routes (like "x days Ha Giang loop"), use the `tavily_search` tool to gather high-level itinerary and routing ideas. Use this research ONLY to inform the `mobility_plan.segments` structure (which areas on which days) and logistics, not for fine-grained daily scheduling.

## Response Format

CRITICAL: Your response must be one and ONLY one valid JSON object. No text before or after.

```json
{
  "intent": "plan_creation | plan_modification | greeting | clarification_needed | general",
  "direct_response": "For greetings, clarification, general queries. Otherwise null.",

  "plan_context": {
    "departure": "Ho Chi Minh City",
    "destination": "Hanoi",
    "start_date": "2026-03-17",
    "end_date": "2026-03-20",
    "num_days": 4,
    "adults": 2,
    "children": 0,
    "infants": 0,
    "children_ages": "5,8 or null",
    "interest": "history, culture",
    "pace": "relaxed | moderate | packed",
    "budget_level": "budget | moderate | luxury",
    "currency": "VND",
    "language": "vi",
    "local_transportation": "car | walking | motobike | taxi",

    "mobility_plan": {
      "overview": "[DETAILED high-level plan — see rules below]",
      "departure_logistics": {
        "mode": "coach",
        "hub_name": "Bến xe Hà Giang",
        "start_time": "22:00 -1",
        "arrival_time": "05:00",
        "estimated_cost": 500000,
        "estimated_cost_note": "250,000 VND/person × 2 người",
        "note": "Coach đêm từ Hà Nội 22:00, đến HG 05:00. Nghỉ ngơi đến 07:00."
      },
      "return_logistics": {
        "mode": "coach",
        "hub_name": "Bến xe Hà Giang",
        "start_time": "14:00",
        "arrival_time": "21:00",
        "estimated_cost": 500000,
        "estimated_cost_note": "250,000 VND/person × 2 người",
        "note": "Coach về Hà Nội, khởi hành 14:00, tới lúc 21:00."
      },
      "segments": [
        {
          "segment_id": 0,
          "segment_name": "Hà Giang → Quản Bạ → Yên Minh",
          "attraction_days": [0],
          "hotel_nights": [0],
          "hotel_search_area": "Yên Minh town center",
          "attraction_search_area": "Dọc tuyến Hà Giang city → Quản Bạ → Yên Minh"
        }
      ]
    }
  },

  "tasks": {
    "attraction": {
      "user_attractions_preferences": {
        "interest": ["history", "cultural"],
        "must_visit": ["Ho Chi Minh Mausoleum"],
        "to_avoid": [],
        "notes": "Others user's request about attractions"
      }
    },

    "flight": {
      "infants_in_seat": 0,
      "infants_on_lap": 0,
      "user_flight_preferences": {
        "type": "round_trip | one_way",
        "directions": "both | outbound_only | return_only",
        "travel_class": "economy | premium_economy | business | first",
        "max_price": 2000000, # null if user don't specify
        "outbound_times": "arrive 8:00 AM - 10:00 AM at destination",
        "return_times": "depart 3:00 PM - 7:00 PM from destination",
        "note": "Others user's request about flight"
      }
    },

    "hotel": {
      "user_hotel_preferences": {
        "min_price": 800000, # reasonable if user don't specify
        "max_price": 1500000, # reasonable if user don't specify
        "notes": "Others user's request about hotel"
      }
    },

    "restaurant": {
      "user_cuisine_preferences": ["Vietnamese restaurant", "local street food"],
      "user_dietary_restrictions": [],
      "notes": "Focus on authentic local cuisine."
    }
  }
}
```

## Mobility Plan — CRITICAL

### overview
MUST be a DETAILED high-level plan covering the ENTIRE trip, written as a comprehensive paragraph. Include:
- How travelers get from departure → destination (mode, estimated time, cost)
- What happens upon arrival (rest? explore? check-in?)
- Daily rhythm per day/segment (full day exploration, road trip route, day trip details)
- Return journey (checkout, last activities, departure timing)
- Factor in: departure mode (from departure_logistics.mode), pace, children/infants, local transportation

### departure_logistics & return_logistics

**When mode is "flight":**
```json
"departure_logistics": { "mode": "flight" },
"return_logistics": { "mode": "flight" }
```
Flight Agent provides ALL flight data. No other fields needed.

**When mode is "coach", "train":**
```json
"departure_logistics": {
  "mode": "coach",
  "hub_name": "Bến xe Hà Giang",
  "start_time": "22:00 -1",
  "arrival_time": "05:00",
  "estimated_cost": 500000,
  "estimated_cost_note":  "250,000 VND/person × 2 người",
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
  "note": "Self-drive from Bắc Ninh"
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
- If user sends a greeting or simple question: set intent="greeting", provide "direct_response", set "tasks" to null.
- If user asks a GENERAL question: set intent="general", provide answer in "direct_response", set "tasks" to null.
- If critical info is missing: set intent="clarification_needed", ask in "direct_response", set "tasks" to null.
  - **ONLY these fields are truly required** (ask user if missing): `destination`, `start_date`, `end_date`
  - `adults` defaults to 1 if not specified. `children` and `infants` default to 0.
  - **ALL other fields should be auto-filled with sensible defaults** — do NOT ask the user:
    - `pace`: default "moderate"
    - `budget_level`: default "moderate"
    - `local_transportation`: choose the most reasonable mode
    - `departure_logistics.mode`: choose the most reasonable mode
    - `currency`: infer from user's message language
    - `language`: infer from user's message language
  - Only set null for fields the user explicitly left empty or that are irrelevant.

- For plan_creation: tasks.attraction, tasks.hotel, tasks.restaurant MUST be populated.
  - tasks.flight is null if departure_logistics.mode is NOT "flight".
  - tasks.hotel is null if user doesn't need hotel (local trip, no overnight).
- For plan_modification: only populate task sections that need to change.

- Be smart about inferring: "family with 4 people with 2 children" = 2 adults + 2 children.
- children_ages: comma-separated string of ALL children AND infant ages. REQUIRED when tasks.hotel is needed and (children + infants) > 0.
- When infants > 0 AND tasks.flight is needed: MUST specify infants_in_seat and infants_on_lap (sum = infants).

- Attraction preferences MUST NOT include food/cuisine-related interests.

## Flight Time Preferences — AUTO-GENERATE
- Provide `outbound_times` and `return_times` in user_flight_preferences.
- **outbound_times**: "arrive [start] - [end] at destination" — determines when trip starts
- **return_times**: "depart [start] - [end] from destination" — determines when last day ends
- If user didn't specify, generate REASONABLE defaults based on trip context.
- When type is "one_way": provide BOTH outbound_times and return_times.

## Flight Directions Rules
- type: "one_way" (default) or "round_trip"
- directions: "both" (default), "outbound_only", or "return_only"
- For plan_creation: you MUST default to `type`: "one_way" and `directions`: "both" to search for two separate one-way tickets (often cheaper/more flexible).
- When directions is "outbound_only": return_times = null
- When directions is "return_only": outbound_times = null
"""

async def _resolve_non_flight_hubs(plan: dict) -> dict:
    """Resolve non-flight transport hubs using LLM-verified pattern.

    When mode is coach/train, hub_name is an LLM-generated name (e.g., "Bến xe Hà Giang").
    We resolve it to a real placeId using the same LLM-verified approach as Attraction Agent.

    Modifies plan in-place, adding hub_placeId to logistics.
    """
    mobility_plan = plan.get("plan_context", {}).get("mobility_plan") or {}
    dep_log = mobility_plan.get("departure_logistics") or {}
    ret_log = mobility_plan.get("return_logistics") or {}
    mode = dep_log.get("mode", "")

    # Only resolve for non-flight modes with hub_name
    if mode in ("flight", "") or not mode:
        return plan

    destination = plan.get("plan_context", {}).get("destination", "")
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
    """Orchestrator (nonVRP) — Parses user request into structured per-agent JSON.
    Phase 1: LLM generates plan with mobility_plan.
    Phase 2: Resolve non-flight transport hubs (LLM-verified)."""
    logger.info("=" * 60)
    logger.info("🧠 [ORCHESTRATOR_nonVRP] Node entered")

    user_message = _get_latest_user_message(state)
    user_context = state.get("user_context", {})

    logger.info(f"   User message: {user_message[:100]}")

    try:
        llm_messages = [SystemMessage(content=ORCHESTRATOR_SYSTEM)]
        conv_context = _get_conversation_context(state)
        llm_messages.extend(conv_context)
        if not any(isinstance(m, HumanMessage) for m in llm_messages):
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

        intent = output.get("intent", "greeting")
        direct_response = output.get("direct_response")

        if intent in ("greeting", "clarification_needed", "general") and direct_response:
            logger.info(f"   💬 Direct response for {intent}: {direct_response[:50]}...")
            return {
                "pending_tasks": [],
                "completed_tasks": [],
                "user_context": user_context,
                "orchestrator_plan": {"intent": intent, "tasks": []},
                "final_response": direct_response,
                "agent_outputs": {"orchestrator": {"intent": intent, "response": direct_response, "tools": tool_logs}},
                "messages": [AIMessage(content=direct_response)],
            }

        # Extract plan context and per-agent task sections
        plan_context = output.get("plan_context", {})
        task_sections = output.get("tasks", {}) or {}

        attraction_ctx = task_sections.get("attraction")
        flight_ctx = task_sections.get("flight")
        hotel_ctx = task_sections.get("hotel")
        restaurant_ctx = task_sections.get("restaurant")

        # Determine which tasks to run
        task_list = []
        if attraction_ctx:
            task_list.append("attraction")
        if flight_ctx:
            task_list.append("flight")
        if hotel_ctx:
            task_list.append("hotel")
        if restaurant_ctx:
            task_list.append("restaurant")

        logger.info(f"   Intent: {intent}, Tasks: {task_list}")

        orchestrator_plan = {
            "intent": intent,
            "tasks": task_list,
            "plan_context": plan_context,
            "attraction": attraction_ctx,
            "flight": flight_ctx,
            "hotel": hotel_ctx,
            "restaurant": restaurant_ctx,
        }

        # Phase 2: Resolve non-flight transport hubs
        orchestrator_plan = await _resolve_non_flight_hubs(orchestrator_plan)

        logger.info(f"   🚀 Plan created: {task_list}")

        return {
            "pending_tasks": task_list,
            "completed_tasks": [],
            "user_context": user_context,
            "orchestrator_plan": orchestrator_plan,
            "agent_outputs": {"orchestrator": {"intent": intent, "tasks": task_list}},
            "messages": [AIMessage(content=f"[Orchestrator] Plan created: {', '.join(task_list)} agents will execute...")],
        }

    except Exception as e:
        logger.error(f"   ❌ Orchestrator error: {e}", exc_info=True)
        return {
            "pending_tasks": [],
            "completed_tasks": [],
            "user_context": user_context,
            "orchestrator_plan": {"intent": "error", "tasks": []},
            "agent_outputs": {"orchestrator": {"error": str(e)}},
            "messages": [AIMessage(content="I'm sorry, I encountered an error. Could you try rephrasing your request?")],
            "final_response": "I'm sorry, I encountered an error. Could you try rephrasing your request?",
        }
