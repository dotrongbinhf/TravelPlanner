import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _get_latest_user_message, _get_conversation_context
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import settings

from src.agents.nodes.orchestratorMock import Orchestrator_Mock

logger = logging.getLogger(__name__)

llm_orchestrator = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.3,
    streaming=False,
)

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

CRITICAL: Whatever user request is, Your response must be one and ONLY one valid JSON object. No text before or after. Just the raw JSON starting with { and ending with }.
EXAMPLE JSON - OUTPUT STRUCTURE:
{
  "intent": "plan_creation | plan_modification | greeting | clarification_needed | general",
  "direct_response": "For greetings, clarification questions, or general queries, write your natural language response to the user here. Otherwise null.",

  "plan_context": {
    "departure": "Ho Chi Minh City",
    "travel_by": "flight | car | train | coach | motobike | taxi",
    "mobility_plan": "Depart from Ho Chi Minh City in the morning and arrive in Hanoi before noon of the first day. Depart from Hanoi in the afternoon of the last day to return to Ho Chi Minh City.",
    "destination": "Hanoi",
    "local_transportation": "car | walking | motobike | taxi",
    "start_date": "2026-03-17",
    "end_date": "2026-03-20",
    "num_days": 4,
    "adults": 2,
    "children": 0,
    "infants": 0,
    "children_ages": "5,8 or null (include children and infants ages)",
    "interest": "history, culture",
    "pace": "relaxed | moderate | packed",
    "budget_level": "budget | moderate | luxury",
    "currency": "VND",
    "geographic_type": "centralized | centralized_with_outlier | road_trip",
  },

  "tasks": {
    "attraction": {
      "segments": [
        {
          "segment_name": "Central Hanoi",
          "days": [1, 2, 4],
          "area_description": "Central Hanoi districts and nearby",
        },
        {
          "segment_name": "Ba Vì excursion",
          "days": [3],
          "area_description": "Ba Vì district, ~60km west of Hanoi center",
        }
      ],
      "notes": "Day 1 is arrival day. Day 3 is dedicated to Ba Vi with an overnight stay. Day 4 is for departure."
      "user_attractions_preferences": {
        "interest": ["history", "cultural"],
        "must_visit": ["Ho Chi Minh Mausoleum", "Temple of Literature"],
        "to_avoid": [],
        "notes": "Others user's request about attractions"
      }
    },

    "flight": {
      "departure_airport_hint": "Tân Sơn Nhất (SGN)",
      "destination_airport_hint": "Nội Bài (HAN)",
      "infants_in_seat": 0,
      "infants_on_lap": 0,
      "user_flight_preferences": {
        "type": "round_trip | one_way",
        "travel_class": "economy | premium_economy | business | first",
        "max_price": 2000000,
        "outbound_times": "4:00 AM - 7:00 AM departure",
        "return_times": "4:00 PM - 7:00 PM departure",
        "note": "Others user's request about flight"
      }
    },

    "hotel": {
      "user_hotel_preferences": {
        "min_price": 800000,
        "max_price": 1500000,
        "notes": "Others user's request about hotel"
      },
      "hotel_segments": [
        {
          "segment_name": "Central Hanoi Stay",
          "search_area": "Hoàn Kiếm district or Old Quarter, Hanoi",
          "check_in": "2026-03-17",
          "check_out": "2026-03-19",
          "nights": 2,
          "notes": "Convenient access to historical sites and city attractions."
        },
        {
          "segment_name": "Ba Vi Stay",
          "search_area": "Near Ba Vi National Park entrance or within the park if options exist",
          "check_in": "2026-03-19",
          "check_out": "2026-03-20",
          "nights": 1,
          "notes": "To fully experience Ba Vi National Park and avoid long travel times."
        }
      ]
    },

    "restaurant": {
      "user_cuisine_preferences": ["Vietnamese restaurant", "local street food"],
      "user_dietary_restrictions": [],
      "notes": "Focus on authentic local cuisine — phở, bún chả, bánh mì, etc."
    }
  }
}

## Rules
- CRITICAL: Whatever user request is, Your response must be one and ONLY one valid JSON object. No text before or after. Just the raw JSON starting with { and ending with }.
- If user sends a greeting or simple question: set intent="greeting", provide a warm "direct_response", set "tasks" to null.
- If user asks a GENERAL question (translate, summarize, explain, etc.): set intent="general", provide the answer in "direct_response", set "tasks" to null.
- If critical info is genuinely missing or you don't understand the user request: set intent="clarification_needed", provide the question in "direct_response", set "tasks" to null.

- For plan_creation: tasks.attraction, tasks.hotel, tasks.restaurant MUST be populated. tasks.flight is null if user doesn't need flight suggestion or travel_by is not "flight". tasks.hotel is null if user doesn't need hotel or accommodation suggestion
- For plan_modification: only populate task sections that need to change.

- Be smart about inferring: "family with 4 people with 2 children" = 2 adults + 2 children.
- children_ages in plan_context: This is a comma-separated string of ages for ALL children AND infants combined (children ages first, then infant ages). REQUIRED when task.hotel is needed and (children + infants) > 0. If ages are unknown, ask the user via clarification_needed.
- When infants > 0 AND tasks.flight is needed: MUST specify infants_in_seat and infants_on_lap (their sum MUST equal plan_context.infants). If user doesn't specify, default all infants to infants_on_lap.

- You MUST separate user interests into domain-specific preferences.
- Attraction preferences MUST NOT include food/cuisine-related interests.

- For CENTRALIZED: only 1 segment in attraction. hotel_segments has 1 entry.
- For CENTRALIZED_WITH_OUTLIER: multiple segments. hotel_segments has entries per overnight area.
- For ROAD_TRIP: segments follow the route order. hotel_segments has 1 entry per night stop.

- Important: Fields that are not specified by the user should EXPLICITLY appear in the JSON with value null. Do NOT omit them. Do NOT replace them with guessed values.

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

        result = await llm_orchestrator.ainvoke(llm_messages)
        output = _extract_json(result.content)
        # output = _extract_json(Orchestrator_Mock)

        intent = output.get("intent", "greeting")
        direct_response = output.get("direct_response")

        if intent in ("greeting", "clarification_needed", "general") and direct_response:
            logger.info(f"   💬 Direct response for {intent}: {direct_response[:50]}...")
            return {
                "current_agent": "orchestrator",
                "current_tool": "",
                "pending_tasks": [],
                "completed_tasks": [],
                "user_context": user_context,
                "orchestrator_plan": {"intent": intent, "tasks": []},
                "final_response": direct_response,
                "agent_outputs": {"orchestrator": {"intent": intent, "response": direct_response}},
                "messages": [AIMessage(content=direct_response)],
            }

        # Fallback if no direct_response but intent is non-plan
        # if intent == "greeting" or not tasks:
        #     logger.info("   👋 Greeting Fallback (no direct_response from LLM)")
        #     greeting = "Hello! I'm your travel planning assistant. How can I help you plan your trip today?"
        #     return {
        #         "current_agent": "orchestrator",
        #         "current_tool": "",
        #         "pending_tasks": [],
        #         "completed_tasks": [],
        #         "user_context": user_context,
        #         "orchestrator_plan": {"intent": intent, "tasks": []},
        #         "final_response": greeting,
        #         "agent_outputs": {"orchestrator": {"intent": intent}},
        #         "messages": [AIMessage(content=greeting)],
        #     }

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

        # Plan creation — build orchestrator_plan with plan_context + per-agent sections
        orchestrator_plan = {
            "intent": intent,
            "tasks": task_list,
            "plan_context": plan_context,
            "attraction": attraction_ctx,
            "flight": flight_ctx,
            "hotel": hotel_ctx,
            "restaurant": restaurant_ctx,
        }

        logger.info(f"   🚀 Plan created: {task_list}")

        return {
            "current_agent": "orchestrator",
            "current_tool": "",
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
            "current_agent": "orchestrator",
            "current_tool": "",
            "pending_tasks": [],
            "completed_tasks": [],
            "user_context": user_context,
            "orchestrator_plan": {"intent": "error", "tasks": []},
            "agent_outputs": {"orchestrator": {"error": str(e)}},
            "messages": [AIMessage(content="I'm sorry, I encountered an error. Could you try rephrasing your request?")],
            "final_response": "I'm sorry, I encountered an error. Could you try rephrasing your request?",
        }


