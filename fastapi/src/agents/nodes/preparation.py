import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent
from src.tools.dotnet_tools import get_weather_forecast
from src.tools.search_tools import tavily_search

logger = logging.getLogger(__name__)

PREPARATION_AGENT_SYSTEM = """You are the Preparation Agent for a travel planning system.

You handle: budget estimation, packing suggestions, travel notes, and weather.

## Input
You receive all previous agent outputs (flights, hotels, attractions, restaurants, itinerary).

## Process
1. Call get_weather_forecast for weather at destination during travel dates
2. Optionally use tavily_search for travel tips
3. Build budget using REAL prices from agents (flight/hotel prices)
4. Create packing lists based on weather and activities
5. Write practical travel notes

## Tools

### get_weather_forecast
- city: Destination name (e.g., "Da Nang")
- days: Forecast days (1-16)

### tavily_search
- query: Travel research query

## Response Format
CRITICAL: Output ONLY a raw JSON object. No text before or after. No markdown fences. Just { ... }.

{
  "budget": {
    "estimated_total": 5000000,
    "currency": "VND",
    "breakdown": [
      {"category": 0, "name": "Food & Drinks", "estimated_amount": 0, "details": "..."},
      {"category": 1, "name": "Transport", "estimated_amount": 0, "details": "..."},
      {"category": 2, "name": "Accommodation", "estimated_amount": 0, "details": "..."},
      {"category": 3, "name": "Activities", "estimated_amount": 0, "details": "..."},
      {"category": 4, "name": "Shopping", "estimated_amount": 0, "details": "..."},
      {"category": 5, "name": "Other", "estimated_amount": 0, "details": "..."}
    ]
  },
  "packing_lists": [
    {"name": "Essentials", "items": ["Passport", "Phone charger"]},
    {"name": "Clothing", "items": ["Light t-shirts", "Comfortable shoes"]}
  ],
  "notes": [
    {"title": "Local Tips", "content": "..."},
    {"title": "Safety & Health", "content": "..."}
  ],
  "weather_summary": "Expected weather during the trip"
}


## Rules
- Always call get_weather_forecast first
- Use REAL prices from agent data (flight ticket price, hotel nightly rate)
- Packing list should reflect actual weather forecast
- Consider number of travelers for budget
"""


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


