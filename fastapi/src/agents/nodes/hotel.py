import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent
from src.tools.dotnet_tools import search_hotels
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import settings

logger = logging.getLogger(__name__)

llm_hotel = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)

HOTEL_AGENT_SYSTEM = """You are the Hotel Agent for a travel planning system.

You find hotels using the search_hotels tool.

## Input
You receive two pieces of context from the Orchestrator:
1. **plan_context**: Shared trip info (destination, dates, passengers, budget, currency, mobility_plan)
2. **hotel context**: Hotel-specific info (strategy: single_hotel or multi_hotel, segments with check_in/check_out/area hints, guests, budget preferences, hotel_class)

## Process
1. Read both plan_context and hotel context carefully
2. For EACH segment in the hotel context:
   a. Build a search query targeting the segment's area/destination
   b. Call search_hotels with the segment's check_in_date, check_out_date, guests, and any filters (hotel_class, max_price)
   c. From the results, analyze all hotels considering: location, price, rating, reviews, nearby places, amenities, and user preferences
   d. Choose the BEST hotel for that segment
3. Return the final JSON

## Tool: search_hotels
Key parameters:
- query: Search text with area - one area per call only (e.g., "Hotel in Hoàn Kiếm, Hà Nội") (REQUIRED)
- check_in_date: YYYY-MM-DD (REQUIRED)
- check_out_date: YYYY-MM-DD (REQUIRED)
- adults: Number of adult guests (REQUIRED)
- children: TOTAL count of children + infants from plan_context (REQUIRED)
- children_ages: Comma-separated ages for ALL children+infants (e.g. "1,5,8"). The count MUST match the children parameter. Use age 1 for infants whose exact age is unknown. REQUIRED when children > 0.
- currency: Currency code (default "USD")
- hotel_class: Star filter (list of stars comma separated like "3" or "3,4,5")
- sort_by: 3=Lowest price, 8=Highest rating, 13=Most reviewed

## Response Format
CRITICAL: If your next step is to use a tool, return your response to call the tool. If you don't need to use tools anymore, your response must be one and ONLY one valid JSON object. No text before or after. Just the raw JSON starting with { and ending with }.

EXAMPLE - FINAL OUTPUT STRUCTURE:
{
  "segments": [
    {
      "segment_name": "same as segment_name in hotel context",
      "check_in": "2026-03-20",
      "check_out": "2026-03-23",
      "recommend_hotel_name": "Hanoi La Siesta Hotel & Spa",
      "recommend_note": "The reason why you choose this hotel for this segment"
    }
  ]
}

## Rules
- Always call search_hotels — do NOT make up hotel data
- For multi_hotel (multiple segments): run separate searches per segment
- Choose hotels based on the actual search results, prioritizing: rating, location, price-to-value ratio
- Use the EXACT hotel name as it appears in the search results
- Do NOT output your final JSON until ALL segments have been searched
"""

async def hotel_agent_node(state: GraphState) -> dict[str, Any]:
    """Hotel Agent — Searches hotels per segment. Runs in Phase 2."""
    logger.info("=" * 60)
    logger.info("🏨 [HOTEL_AGENT] Node entered (Phase 2)")

    plan = state.get("orchestrator_plan", {})
    plan_context = plan.get("plan_context", {})
    hotel_ctx = plan.get("hotel", {})

    if not hotel_ctx:
        logger.info("   No hotel context → skip")
        return {
            "current_agent": "hotel_agent",
            "agent_outputs": {"hotel_agent": {"hotels_found": False, "skipped": True}},
            "messages": [AIMessage(content="[Hotel Agent] No hotel search needed")],
        }

    hotel_result = {}

    try:
        human_content = f"""Plan context (shared trip info):
{json.dumps(plan_context, indent=2, ensure_ascii=False)}

Hotel-specific context:
{json.dumps(hotel_ctx, indent=2, ensure_ascii=False)}

Search for hotels based on this context. Use the plan_context for dates, passengers, and budget info. Use the hotel context for segments, area hints, guests, and preferences."""

        llm_messages = [
            SystemMessage(content=HOTEL_AGENT_SYSTEM),
            HumanMessage(content=human_content),
        ]

        result, tool_logs = await _run_agent_with_tools(
            llm=llm_hotel, messages=llm_messages,
            tools=[search_hotels], max_iterations=5,
            agent_name="HOTEL_AGENT",
        )
        hotel_result = _extract_json(result.content)
        hotel_result["tools"] = tool_logs

    except Exception as e:
        logger.error(f"   ❌ Hotel Agent error: {e}", exc_info=True)
        hotel_result = {"hotels_found": False, "error": str(e)}

    logger.info("🏨 [HOTEL_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "hotel_agent",
        "current_tool": "search_hotels",
        "agent_outputs": {"hotel_agent": hotel_result},
        "messages": [AIMessage(content=f"[Hotel Agent] Hotel search completed")],
    }
