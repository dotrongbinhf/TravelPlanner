import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _get_latest_user_message, _get_conversation_context, llm_fast


logger = logging.getLogger(__name__)

ORCHESTRATOR_SYSTEM = """You are the Orchestrator Agent for a multi-agent travel planning system.

Your PRIMARY job is to:
1. Understand the user's travel request
2. Ask clarification if critical info is missing
3. Analyze the destination geography to determine the planning strategy
4. Create a structured plan with SPECIFIC CONTEXT for each specialist agent

## Geographic Intelligence — CRITICAL

You MUST classify the trip into one of 3 geographic types. This determines how ALL agents plan.

### Type 1: CENTRALIZED
When: All or most relevant attractions are in ONE compact area (e.g., exploring central Hanoi for history/culture, Bangkok city tour, Da Nang city).
- Attraction Agent: Search for best attractions matching user interests in the central area. No rigid per-day area assignment — let the Attraction Agent choose the best places freely.
- Hotel Agent: Search 1 hotel in the central/tourist area. Runs INDEPENDENTLY (does not need Attraction results).
- Example: "Travel Hanoi for 4 days, interested in history and culture" → attractions all in central Hanoi → 1 hotel in Hoàn Kiếm/Ba Đình area.

### Type 2: CENTRALIZED_WITH_OUTLIER
When: Most attractions are in a central area, BUT the user also requires visiting a distant location (e.g., Ba Vì, Ninh Bình day trip from Hanoi).
- Split the trip into SEGMENTS: main segment in center + outlier segment(s) at distant location(s).
- Attraction Agent: Gets segments with areas — find attractions in each segment's area.
- Hotel Agent: Multi-hotel strategy — hotel in center for main days + hotel near outlier for outlier day(s).
- Example: "Travel Hanoi 4 days, must visit Ba Vì" → 3 days center Hanoi + 1 day Ba Vì → hotel 2 nights center + 1 night near Ba Vì.

### Type 3: ROAD_TRIP
When: Attractions are spread far apart along a route (e.g., Hà Giang loop, coastal road trip).
- Plan as a route with STOPS per day/night.
- Attraction Agent: Find attractions ALONG THE ROUTE between stops.
- Hotel Agent: 1 hotel per night at each stop location.
- Example: "Hà Giang 4 days" → Day 1: Hanoi→Ha Giang city→Quản Bạ, Day 2: Quản Bạ→Đồng Văn, Day 3: Đồng Văn→Mèo Vạc, Day 4: Mèo Vạc→Ha Giang city→Hanoi.

## Response Format

CRITICAL: Your response must be ONLY a valid JSON object. No text before or after. Just the raw JSON starting with { and ending with }.
EXAMPLE JSON:
{
  "intent": "plan_creation | plan_modification | greeting | clarification_needed | general_query",
  "clarification_question": null,

  "attraction": {
    "destination": "Hanoi",
    "start_date": "2026-03-17",
    "end_date": "2026-03-20",
    "num_days": 4,
    "interests": ["history", "culture", "food"],
    "pace": "relaxed | moderate | packed",
    "must_visit": [],
    "places_to_avoid": [],
    "adults": 2,
    "children": 0,
    "infants": 0,
    "budget_level": "budget | moderate | luxury",
    "geographic_type": "centralized | centralized_with_outlier | road_trip",
    "segments": [
      {
        "segment_name": "Central Hanoi",
        "days": [1, 2, 4],
        "area_description": "Central Hanoi districts and nearby",
        "theme": "Historical and cultural landmarks",
      },
      {
        "segment_name": "Ba Vì excursion",
        "days": [3],
        "area_description": "Ba Vì district, ~60km west of Hanoi center",
        "theme": "Nature and mountains",
      }
    ],
    "notes": "Day 1 is arrival day. Day 3 is dedicated to Ba Vi with an overnight stay. Day 4 is for departure."
  },

  "flight": {
    "origin": "Ho Chi Minh City",
    "destination": "Hanoi",
    "origin_airport_hint": "Tân Sơn Nhất (SGN)",
    "destination_airport_hint": "Nội Bài (HAN)",
    "outbound_date": "2026-03-17",
    "return_date": "2026-03-20 or null (MUST be null for one_way)",
    "trip_type": "round_trip | one_way",
    "adults": 2,
    "children": 0,
    "infants": 0,
    "travel_class": "economy | premium_economy | business | first",
    "currency": "VND"
  },

  "hotel": {
    "destination": "Hanoi",
    "adults": 2,
    "children": 0,
    "children_ages": "5,8 or null (REQUIRED when children > 0)",
    "budget_level": "budget | moderate | luxury",
    "currency": "VND",
    "geographic_type": "centralized | centralized_with_outlier | road_trip",
    "hotel_segments": [
      {
        "segment_name": "Central Hanoi Stay",
        "search_area": "Hoàn Kiếm district or Old Quarter, Hanoi",
        "check_in": "2026-03-17",
        "check_out": "2026-03-19",
        "nights": 2,
        "reason": "Convenient access to historical sites and city attractions."
      },
      {
        "segment_name": "Ba Vi Stay",
        "search_area": "Near Ba Vi National Park entrance or within the park if options exist",
        "check_in": "2026-03-19",
        "check_out": "2026-03-20",
        "nights": 1,
        "reason": "To fully experience Ba Vi National Park and avoid long travel times."
      }
    ]
  },

  "restaurant": {
    "destination": "Hanoi",
    "num_days": 4,
    "budget_level": "budget | moderate | luxury",
    "cuisine_preferences": ["Vietnamese restaurant", "local street food"],
    "dietary_restrictions": [],
    "adults": 2,
    "children": 0,
    "notes": "Focus on authentic local cuisine — phở, bún chả, bánh mì, etc."
  },
}

## Rules
- If user sends a greeting or simple question: set intent="greeting", set all agent sections to null.
- If user asks a GENERAL question about the conversation (translate, summarize, explain, etc.) that is NOT a new travel plan: set intent="general_query", set all agent sections to null.
- If critical info is genuinely missing (no destination AND no dates): set intent="clarification_needed", provide clarification_question, set agent sections to null.
- For plan_creation: attraction, hotel, restaurant sections MUST be populated. Flight is null if user doesn't mention transport.
- For plan_modification: only populate sections that need to change.
- When trip_type is one_way: return_date MUST be null.
- When children > 0: ALWAYS include children_ages in the hotel section (ask user if unknown).
- For CENTRALIZED: only 1 segment in attraction. hotel_segments has 1 entry.
- For CENTRALIZED_WITH_OUTLIER: multiple segments. hotel_segments has entries per overnight area.
- For ROAD_TRIP: segments follow the route order. hotel_segments has 1 entry per night stop.
- Be smart about inferring: "family with 4 people with 2 children" = 2 adults + 2 children.
- The EXAMPLE JSON above shows a centralized_with_outlier case. Adapt the segments based on actual geographic analysis and user's preferences.
"""


async def orchestrator_node(state: GraphState) -> dict[str, Any]:
    """Orchestrator — Parses user request into structured per-agent JSON sections."""
    logger.info("=" * 60)
    logger.info("🧠 [ORCHESTRATOR] Node entered")

    user_message = _get_latest_user_message(state)
    user_context = state.get("user_context", {})

    logger.info(f"   User message: {user_message[:100]}")

    try:
        llm_messages = [SystemMessage(content=ORCHESTRATOR_SYSTEM)]
        conv_context = _get_conversation_context(state)
        llm_messages.extend(conv_context)
        if not any(isinstance(m, HumanMessage) for m in llm_messages):
            llm_messages.append(HumanMessage(content=user_message))

        result = await llm_fast.ainvoke(llm_messages)
        output = _extract_json(result.content)

        intent = output.get("intent", "greeting")
        clarification = output.get("clarification_question")

        # Extract per-agent sections
        attraction_ctx = output.get("attraction")
        flight_ctx = output.get("flight")
        hotel_ctx = output.get("hotel")
        restaurant_ctx = output.get("restaurant")

        # Determine which tasks to run
        tasks = []
        if attraction_ctx:
            tasks.append("attraction")
        if flight_ctx:
            tasks.append("flight")
        if hotel_ctx:
            tasks.append("hotel")
        if restaurant_ctx:
            tasks.append("restaurant")

        logger.info(f"   Intent: {intent}, Tasks: {tasks}")

        # Handle clarification
        if intent == "clarification_needed" and clarification:
            logger.info(f"   ❓ Clarification: {clarification}")
            return {
                "current_agent": "orchestrator",
                "current_tool": "",
                "pending_tasks": [],
                "completed_tasks": [],
                "user_context": user_context,
                "orchestrator_plan": {"intent": intent, "tasks": []},
                "final_response": clarification,
                "agent_outputs": {"orchestrator": {"intent": intent, "clarification": clarification}},
                "messages": [AIMessage(content=clarification)],
            }

        # Handle general query (translate, summarize, etc.)
        if intent == "general_query":
            logger.info("   💬 General query → SYNTHESIZE (no specialist agents)")
            return {
                "current_agent": "orchestrator",
                "current_tool": "",
                "pending_tasks": [],
                "completed_tasks": [],
                "user_context": user_context,
                "orchestrator_plan": {"intent": intent, "tasks": []},
                "agent_outputs": {"orchestrator": {"intent": intent}},
                "messages": [AIMessage(content=f"[Orchestrator] General query detected, routing to synthesize...")],
            }

        # Handle greeting
        if intent == "greeting" or not tasks:
            logger.info("   👋 Greeting → SYNTHESIZE")
            greeting = "Hello! I'm your travel planning assistant. How can I help you plan your trip today?"
            return {
                "current_agent": "orchestrator",
                "current_tool": "",
                "pending_tasks": [],
                "completed_tasks": [],
                "user_context": user_context,
                "orchestrator_plan": {"intent": intent, "tasks": []},
                "agent_outputs": {"orchestrator": {"intent": intent}},
                "messages": [AIMessage(content=greeting)],
            }

        # Plan creation — build orchestrator_plan with per-agent sections
        orchestrator_plan = {
            "intent": intent,
            "tasks": tasks,
            "attraction": attraction_ctx,
            "flight": flight_ctx,
            "hotel": hotel_ctx,
            "restaurant": restaurant_ctx,
        }

        logger.info(f"   🚀 Plan created: {tasks}")

        return {
            "current_agent": "orchestrator",
            "current_tool": "",
            "pending_tasks": tasks,
            "completed_tasks": [],
            "user_context": user_context,
            "orchestrator_plan": orchestrator_plan,
            "agent_outputs": {"orchestrator": {"intent": intent, "tasks": tasks}},
            "messages": [AIMessage(content=f"[Orchestrator] Plan created: {', '.join(tasks)} agents will execute...")],
        }

    except Exception as e:
        logger.error(f"   ❌ Orchestrator error: {e}", exc_info=True)
        return {
            "current_agent": "orchestrator",
            "current_tool": "",
            "pending_tasks": [],
            "completed_tasks": [],
            "user_context": user_context,
            "orchestrator_plan": {"intent": "error", "tasks": []},
            "agent_outputs": {"orchestrator": {"error": str(e)}},
            "messages": [AIMessage(content="I'm sorry, I encountered an error. Could you try rephrasing your request?")],
        }


