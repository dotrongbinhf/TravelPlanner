"""
Agent Nodes for the LangGraph multi-agent travel planner.

Architecture: Orchestrator → [Flight, Attraction] → [Hotel, Restaurant] → Itinerary → Preparation → Synthesize

Phase 1 (parallel): Flight + Attraction — both independent, run first
Phase 2 (parallel): Hotel + Restaurant — both use Attraction Agent's output (areas + coordinates)
Phase 3 (sequential): Itinerary → Preparation → Synthesize
"""

import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.agents.state import GraphState
from src.agents.prompts import (
    ORCHESTRATOR_SYSTEM,
    HOTEL_AGENT_SYSTEM,
    FLIGHT_AGENT_SYSTEM,
    ATTRACTION_AGENT_SYSTEM,
    RESTAURANT_AGENT_SYSTEM,
    PREPARATION_AGENT_SYSTEM,
    ITINERARY_AGENT_SYSTEM,
    SYNTHESIZE_SYSTEM,
)
from src.tools.dotnet_tools import (
    search_hotels,
    search_airports,
    search_flights,
    get_weather_forecast,
)
from src.tools.search_tools import tavily_search
from src.tools.maps_tools import (
    places_text_search_id_only,
    get_google_place_details,
    places_nearby_search,
    get_distance_matrix,
)
from src.tools.place_resolver import resolve_place, resolve_places
from src.tools.itinerary_tools import optimize_daily_itinerary
from src.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# LLM Instances
# ============================================================

llm_fast = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.3,
    streaming=False,
)

llm_streaming = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.7,
    streaming=True,
)

llm_agent = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)


# ============================================================
# Helper Functions
# ============================================================

def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response text, handling markdown code blocks."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return json.loads(text[start:end].strip())

    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return json.loads(text[start:end].strip())

    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])

    raise ValueError(f"No valid JSON found in LLM response: {text[:200]}...")


def _get_latest_user_message(state: GraphState) -> str:
    """Extract the most recent user message from state."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def _get_conversation_context(state: GraphState, max_messages: int = 10) -> list:
    """Build conversation context from message history."""
    messages = state.get("messages", [])
    context = []
    for msg in messages[-max_messages:]:
        content = msg.content if hasattr(msg, "content") else str(msg)
        if content.startswith("["):
            continue
        if isinstance(msg, HumanMessage):
            context.append(msg)
        elif isinstance(msg, AIMessage):
            context.append(msg)
    return context


async def _run_agent_with_tools(
    llm,
    messages: list,
    tools: list,
    max_iterations: int = 5,
    agent_name: str = "agent",
) -> Any:
    """ReAct tool-calling loop: LLM → tool calls → LLM → ... → final response."""
    tool_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    for iteration in range(max_iterations):
        result = await llm_with_tools.ainvoke(messages)

        if not result.tool_calls:
            logger.info(f"   [{agent_name}] Final response at iteration {iteration + 1}")
            return result

        logger.info(f"   [{agent_name}] Iteration {iteration + 1}: {len(result.tool_calls)} tool call(s)")
        messages.append(result)

        for tool_call in result.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call.get("id", tool_name)

            logger.info(f"   [{agent_name}] Calling: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")

            tool_fn = tool_map.get(tool_name)
            if tool_fn:
                try:
                    tool_result = await tool_fn.ainvoke(tool_args)
                    tool_result_str = json.dumps(tool_result, default=str, ensure_ascii=False)
                    if len(tool_result_str) > 4000:
                        tool_result_str = tool_result_str[:4000] + "...(truncated)"
                    messages.append(ToolMessage(content=tool_result_str, tool_call_id=tool_id))
                except Exception as e:
                    logger.error(f"   [{agent_name}] Tool {tool_name} error: {e}")
                    messages.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_id))
            else:
                messages.append(ToolMessage(content=f"Unknown tool: {tool_name}", tool_call_id=tool_id))

    logger.warning(f"   [{agent_name}] Max iterations reached, forcing final response")
    result = await llm.ainvoke(messages)
    return result


# ============================================================
# 1. Orchestrator Node
# ============================================================

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


# ============================================================
# 2. Attraction Agent Node (Phase 1)
# ============================================================

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


# ============================================================
# 3. Flight Agent Node (Phase 1)
# ============================================================

async def flight_agent_node(state: GraphState) -> dict[str, Any]:
    """Flight Agent — Airport + flight search. Runs in Phase 1 (parallel with Attraction)."""
    logger.info("=" * 60)
    logger.info("✈️ [FLIGHT_AGENT] Node entered (Phase 1)")

    plan = state.get("orchestrator_plan", {})
    ctx = plan.get("flight", {})

    if not ctx:
        logger.info("   No flight context → skip")
        return {
            "current_agent": "flight_agent",
            "agent_outputs": {"flight_agent": {"flights_found": False, "skipped": True}},
            "messages": [AIMessage(content="[Flight Agent] No flight search needed")],
        }

    flight_result = {}

    try:
        llm_messages = [
            SystemMessage(content=FLIGHT_AGENT_SYSTEM),
            HumanMessage(content=f"""
Orchestrator's flight context:
{json.dumps(ctx, indent=2, ensure_ascii=False)}

Please search for airports and flights based on this context.
"""),
        ]

        result = await _run_agent_with_tools(
            llm=llm_agent, messages=llm_messages,
            tools=[search_airports, search_flights], max_iterations=4,
            agent_name="FLIGHT_AGENT",
        )
        flight_result = _extract_json(result.content)

    except Exception as e:
        logger.error(f"   ❌ Flight Agent error: {e}", exc_info=True)
        flight_result = {"flights_found": False, "error": str(e)}

    logger.info("✈️ [FLIGHT_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "flight_agent",
        "current_tool": "search_flights",
        "agent_outputs": {"flight_agent": flight_result},
        "messages": [AIMessage(content=f"[Flight Agent] {flight_result.get('search_summary', 'Flight search completed')}")],
    }


# ============================================================
# 4. Hotel Agent Node (Phase 2 — after Attraction)
# ============================================================

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


# ============================================================
# 5. Restaurant Agent Node (Phase 2 — after Attraction)
# ============================================================

async def restaurant_agent_node(state: GraphState) -> dict[str, Any]:
    """Restaurant Agent — Finds restaurants near attraction areas. Runs in Phase 2."""
    logger.info("=" * 60)
    logger.info("🍽️ [RESTAURANT_AGENT] Node entered (Phase 2)")

    plan = state.get("orchestrator_plan", {})
    ctx = plan.get("restaurant", {})
    agent_outputs = state.get("agent_outputs", {})
    attraction_data = agent_outputs.get("attraction_agent", {})

    if not ctx:
        logger.info("   No restaurant context → skip")
        return {
            "current_agent": "restaurant_agent",
            "agent_outputs": {"restaurant_agent": {"restaurants": [], "skipped": True}},
            "messages": [AIMessage(content="[Restaurant Agent] No restaurant search needed")],
        }

    destination = ctx.get("destination", "")
    restaurant_result = {}

    # Build per-day attraction areas for restaurant proximity
    area_distribution = attraction_data.get("area_distribution", {})
    attractions_by_day = {}
    for attr in attraction_data.get("attractions", []):
        day = attr.get("suggested_day", 0)
        if day not in attractions_by_day:
            attractions_by_day[day] = []
        summary = {
            "name": attr.get("name"),
            "area": attr.get("area"),
        }
        loc = attr.get("location", {})
        if loc and loc.get("coordinates"):
            summary["coordinates"] = loc["coordinates"]
        attractions_by_day[day].append(summary)

    try:
        llm_messages = [
            SystemMessage(content=RESTAURANT_AGENT_SYSTEM),
            HumanMessage(content=f"""
Orchestrator's restaurant context:
{json.dumps(ctx, indent=2, ensure_ascii=False)}

Attractions by day (search restaurants NEAR these areas):
{json.dumps(attractions_by_day, indent=2, ensure_ascii=False, default=str)[:3000]}

Area distribution summary:
{json.dumps(area_distribution, indent=2, ensure_ascii=False)}

Find restaurants in the SAME AREA as each day's attractions.
Use the search tools to find real restaurants.
"""),
        ]

        result = await _run_agent_with_tools(
            llm=llm_agent, messages=llm_messages,
            tools=[places_nearby_search, places_text_search_id_only], max_iterations=4,
            agent_name="RESTAURANT_AGENT",
        )
        restaurant_result = _extract_json(result.content)

        # Resolve restaurant places
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

        restaurants = restaurant_result.get("restaurants", [])
        for rest in restaurants:
            name = rest.get("name", "")
            if name:
                resolved = await resolve_place(
                    place_name=f"{name} {destination}",
                    location_bias=location_bias,
                )
                rest["resolved_place"] = resolved
                if resolved.get("resolved"):
                    rest["place_id"] = resolved.get("placeId", "")
                    rest["db_id"] = resolved.get("id", "")
                    rest["location"] = resolved.get("location", {})

        restaurant_result["resolved_count"] = sum(1 for r in restaurants if r.get("place_id"))
        logger.info(f"   Found {len(restaurants)} restaurants, resolved {restaurant_result['resolved_count']}")

    except Exception as e:
        logger.error(f"   ❌ Restaurant Agent error: {e}", exc_info=True)
        restaurant_result = {"error": str(e), "restaurants": []}

    logger.info("🍽️ [RESTAURANT_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "restaurant_agent",
        "current_tool": "place_resolver",
        "agent_outputs": {"restaurant_agent": restaurant_result},
        "messages": [AIMessage(content=f"[Restaurant Agent] Found {len(restaurant_result.get('restaurants', []))} restaurants")],
    }


# ============================================================
# 6. Itinerary Agent Node (Phase 3)
# ============================================================

async def itinerary_agent_node(state: GraphState) -> dict[str, Any]:
    """Itinerary Agent — VRP-optimized daily schedules using all agent data."""
    logger.info("=" * 60)
    logger.info("📅 [ITINERARY_AGENT] Node entered (Phase 3)")

    agent_outputs = state.get("agent_outputs", {})
    plan = state.get("orchestrator_plan", {})
    attraction_ctx = plan.get("attraction", {})
    num_days = attraction_ctx.get("num_days", 3)
    start_date = attraction_ctx.get("start_date", "")

    attraction_data = agent_outputs.get("attraction_agent", {})
    restaurant_data = agent_outputs.get("restaurant_agent", {})
    hotel_data = agent_outputs.get("hotel_agent", {})
    flight_data = agent_outputs.get("flight_agent", {})

    all_attractions = attraction_data.get("attractions", [])
    all_restaurants = restaurant_data.get("restaurants", [])

    itinerary_result = {"daily_schedules": []}

    try:
        # Build compact summaries
        attraction_summaries = [{
            "name": a.get("name"),
            "category": a.get("category"),
            "duration": a.get("suggested_duration_minutes", 60),
            "time_pref": a.get("suggested_time_window", "flexible"),
            "suggested_day": a.get("suggested_day"),
            "area": a.get("area", ""),
            "coordinates": a.get("location", {}).get("coordinates") if a.get("location") else None,
        } for a in all_attractions]

        restaurant_summaries = [{
            "name": r.get("name"),
            "meal_type": r.get("meal_type"),
            "suggested_day": r.get("suggested_day"),
            "area": r.get("area", ""),
            "coordinates": r.get("location", {}).get("coordinates") if r.get("location") else None,
        } for r in all_restaurants]

        hotel_summary = {}
        recs = hotel_data.get("recommendations", [])
        if recs:
            h = recs[0]
            hotel_summary = {
                "name": h.get("name"),
                "area": h.get("area", ""),
                "coordinates": h.get("location", {}).get("coordinates") if h.get("location") else None,
            }

        llm_messages = [
            SystemMessage(content=ITINERARY_AGENT_SYSTEM),
            HumanMessage(content=f"""
Create optimized daily schedules for a {num_days}-day trip starting {start_date}.

Attractions ({len(attraction_summaries)} total):
{json.dumps(attraction_summaries, indent=2, ensure_ascii=False)[:3000]}

Restaurants ({len(restaurant_summaries)} total):
{json.dumps(restaurant_summaries, indent=2, ensure_ascii=False)[:2000]}

Hotel: {json.dumps(hotel_summary, indent=2, ensure_ascii=False)}

Flight info: {json.dumps(flight_data.get('recommendations', []), default=str, ensure_ascii=False)[:500]}

IMPORTANT: Respect the suggested_day assignments. Optimize the ORDER within each day using the tools if coordinates are available.
"""),
        ]

        result = await _run_agent_with_tools(
            llm=llm_agent, messages=llm_messages,
            tools=[get_distance_matrix, optimize_daily_itinerary], max_iterations=4,
            agent_name="ITINERARY_AGENT",
        )
        itinerary_result = _extract_json(result.content)

    except Exception as e:
        logger.error(f"   ❌ Itinerary Agent error: {e}", exc_info=True)
        itinerary_result = {"error": str(e), "daily_schedules": []}

    logger.info("📅 [ITINERARY_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "itinerary_agent",
        "current_tool": "optimize_daily_itinerary",
        "agent_outputs": {"itinerary_agent": itinerary_result},
        "messages": [AIMessage(content=f"[Itinerary Agent] Created {num_days}-day schedule")],
    }


# ============================================================
# 7. Preparation Agent Node (Phase 3)
# ============================================================

async def preparation_agent_node(state: GraphState) -> dict[str, Any]:
    """Preparation Agent — Budget, packing, weather, notes."""
    logger.info("=" * 60)
    logger.info("🎒 [PREPARATION_AGENT] Node entered (Phase 3)")

    agent_outputs = state.get("agent_outputs", {})
    plan = state.get("orchestrator_plan", {})
    attraction_ctx = plan.get("attraction", {})

    destination = attraction_ctx.get("destination", "")
    num_days = attraction_ctx.get("num_days", 3)
    start_date = attraction_ctx.get("start_date", "")
    end_date = attraction_ctx.get("end_date", "")
    adults = attraction_ctx.get("adults", 2)
    children = attraction_ctx.get("children", 0)
    budget_level = attraction_ctx.get("budget_level", "moderate")
    currency = plan.get("hotel", {}).get("currency", "USD")

    attraction_data = agent_outputs.get("attraction_agent", {})
    restaurant_data = agent_outputs.get("restaurant_agent", {})
    hotel_data = agent_outputs.get("hotel_agent", {})
    flight_data = agent_outputs.get("flight_agent", {})
    itinerary_data = agent_outputs.get("itinerary_agent", {})

    preparation_result = {}

    try:
        llm_messages = [
            SystemMessage(content=PREPARATION_AGENT_SYSTEM),
            HumanMessage(content=f"""
Trip details:
- Destination: {destination}
- Duration: {num_days} days ({start_date} to {end_date})
- Travelers: {adults} adults, {children} children
- Budget level: {budget_level}, Currency: {currency}

Agent data for budget estimation:
- Attractions: {len(attraction_data.get('attractions', []))} planned
- Restaurants: {len(restaurant_data.get('restaurants', []))} planned
- Hotel: {json.dumps(hotel_data.get('recommendations', [{}])[0] if hotel_data.get('recommendations') else {}, default=str, ensure_ascii=False)[:500]}
- Flight: {json.dumps(flight_data.get('recommendations', [{}])[0] if flight_data.get('recommendations') else {}, default=str, ensure_ascii=False)[:500]}
- Itinerary: {len(itinerary_data.get('daily_schedules', []))} days scheduled

Check weather, estimate budget, create packing lists and travel notes.
"""),
        ]

        result = await _run_agent_with_tools(
            llm=llm_agent, messages=llm_messages,
            tools=[get_weather_forecast, tavily_search], max_iterations=4,
            agent_name="PREPARATION_AGENT",
        )
        preparation_result = _extract_json(result.content)

    except Exception as e:
        logger.error(f"   ❌ Preparation Agent error: {e}", exc_info=True)
        preparation_result = {"error": str(e)}

    logger.info("🎒 [PREPARATION_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "preparation_agent",
        "current_tool": "get_weather_forecast",
        "agent_outputs": {"preparation_agent": preparation_result},
        "messages": [AIMessage(content="[Preparation Agent] Budget, packing, and notes prepared")],
    }


# ============================================================
# 8. Synthesize Agent Node
# ============================================================

async def synthesize_agent_node(state: GraphState) -> dict[str, Any]:
    """Synthesize Agent — Compiles all agent data into final response."""
    logger.info("=" * 60)
    logger.info("📝 [SYNTHESIZE] Node entered")

    agent_outputs = state.get("agent_outputs", {})
    conversation_messages = state.get("messages", [])
    plan = state.get("orchestrator_plan", {})
    intent = plan.get("intent", "greeting")

    # Build context from agent outputs
    context_parts = []
    for agent_name, data in agent_outputs.items():
        if agent_name == "orchestrator":
            continue
        if data and not isinstance(data, str):
            context_parts.append(f"\n--- {agent_name.upper()} ---")
            context_parts.append(json.dumps(data, indent=2, default=str, ensure_ascii=False)[:2000])

    context_str = "\n".join(context_parts) if context_parts else "No specialist data."
    is_simple = intent in ("greeting", "information_query", "clarification_needed") or not context_parts

    system_content = SYNTHESIZE_SYSTEM
    if is_simple:
        system_content += "\n\nSimple query. Respond naturally."
    else:
        system_content += f"\n\nAgent Data:\n{context_str}"

    llm_messages = [SystemMessage(content=system_content)]
    for msg in conversation_messages[-10:]:
        content = msg.content if hasattr(msg, "content") else str(msg)
        if content.startswith("["):
            continue
        if isinstance(msg, HumanMessage):
            llm_messages.append(msg)
        elif isinstance(msg, AIMessage):
            llm_messages.append(msg)

    if not any(isinstance(m, HumanMessage) for m in llm_messages):
        llm_messages.append(HumanMessage(content="Hello"))

    try:
        result = await llm_streaming.ainvoke(llm_messages)
        final_response = result.content
    except Exception as e:
        logger.error(f"   ❌ Synthesize error: {e}")
        final_response = "Sorry, an error occurred. Please try again."

    # Build structured output for frontend
    structured_output = {}
    db_commands = []

    if not is_simple:
        structured_output = {"intent": intent}
        if "attraction_agent" in agent_outputs:
            structured_output["attractions"] = agent_outputs["attraction_agent"].get("attractions", [])
        if "restaurant_agent" in agent_outputs:
            structured_output["restaurants"] = agent_outputs["restaurant_agent"].get("restaurants", [])
        if "hotel_agent" in agent_outputs:
            structured_output["hotels"] = agent_outputs["hotel_agent"].get("recommendations", [])
        if "flight_agent" in agent_outputs:
            structured_output["flights"] = agent_outputs["flight_agent"].get("recommendations", [])
        if "preparation_agent" in agent_outputs:
            prep = agent_outputs["preparation_agent"]
            structured_output["budget"] = prep.get("budget", {})
            structured_output["packing_lists"] = prep.get("packing_lists", [])
            structured_output["notes"] = prep.get("notes", [])
        if "itinerary_agent" in agent_outputs:
            structured_output["daily_schedules"] = agent_outputs["itinerary_agent"].get("daily_schedules", [])

    logger.info("📝 [SYNTHESIZE] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "synthesize",
        "current_tool": "",
        "final_response": final_response,
        "structured_output": structured_output,
        "db_commands": db_commands,
        "messages": [AIMessage(content=final_response)],
    }
