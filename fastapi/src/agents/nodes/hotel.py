import asyncio
import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.tools.dotnet_tools import search_hotels
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from src.config import settings
from src.services.place_resolver import resolve_single_place

logger = logging.getLogger(__name__)

HOTEL_AGENT_MOCK = {
  "segments": [
    {
      "segment_name": "Central Hanoi Stay",
      "check_in": "2026-04-03",
      "check_in_time": "02:00 PM",
      "check_out": "2026-04-06",
      "check_out_time": "12:00 PM",
      "recommend_hotel_name": "The Oriental Jade Hotel",
      "totalRate": 4500000,
      "recommend_note": "Highly rated (4.9/5) and centrally located in the Old Quarter, this hotel offers excellent service and amenities, making it ideal for a family with young children needing comfort and convenience for their Hanoi exploration."
    }
  ]
}

llm_hotel = (
    ChatOpenAI(
        model="google/gemini-3.1-flash-lite-preview",
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview",
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_HOTEL,
        temperature=0.3,
        streaming=False,
    )
)

HOTEL_AGENT_SYSTEM = """You are the Hotel Agent for a travel planning system.

You find hotels using the search_hotels tool.

## Input
You receive two pieces of context from the Orchestrator:
1. **plan_context**: Shared trip info (destination, dates, passengers, budget, currency, mobility_plan with segments)
2. **hotel context**: user_hotel_preferences (min_price, max_price, notes)

## How to determine hotel segments
Read `plan_context.mobility_plan.segments`. For each segment that has `hotel_nights` (non-empty array):
- Use `hotel_search_area` as the search location
- Use `hotel_nights` (0-indexed night numbers) to calculate check-in and check-out dates from `start_date`
  - check_in = start_date + min(hotel_nights) days
  - check_out = start_date + max(hotel_nights) + 1 days
  - Example: start_date="2026-03-17", hotel_nights=[0,1,2] → check_in="2026-03-17", check_out="2026-03-20"

## Process
1. Read plan_context and hotel context carefully
2. Determine hotel segments from mobility_plan.segments (only those with non-empty hotel_nights)
3. For EACH hotel segment:
   a. Build a search query targeting the segment's hotel_search_area
   b. Call search_hotels EXACTLY ONCE for this segment
   c. From the results, pick the BEST hotel based on: rating, price-to-value, user preferences
4. After ALL segments have been searched, return the final JSON immediately

## CRITICAL — Tool Call Rules
- Call search_hotels **EXACTLY ONCE per segment**. Do NOT call it again unless search results are empty.

## Tool: search_hotels
Key parameters:
- query: Search text with area - one area per call only (e.g., "Hotel in Hoàn Kiếm, Hà Nội") (REQUIRED)
- check_in_date: YYYY-MM-DD (REQUIRED)
- check_out_date: YYYY-MM-DD (REQUIRED)
- adults: Number of adult guests (REQUIRED)
- children: TOTAL count of children + infants from plan_context (REQUIRED)
- children_ages: Comma-separated ages for ALL children+infants. REQUIRED when children > 0.
- currency: Currency code (default "USD")
- hotel_class: Star filter (list of stars comma separated like "3" or "3,4,5")
- sort_by: 3=Lowest price, 8=Highest rating, 13=Most reviewed

## Response Format
After you have search results for ALL segments — return ONLY one valid JSON object. No text before or after.

{
  "segments": [
    {
      "segment_name": "same as segment_name from mobility_plan",
      "check_in": "2026-03-20",
      "check_in_time": "02:00 PM",
      "check_out": "2026-03-23",
      "check_out_time": "12:00 PM",
      "recommend_hotel_name": "Hanoi La Siesta Hotel & Spa",
      "totalRate": 4500000,
      "recommend_note": "Reason for choosing this hotel"
    }
  ]
}

## Rules
- totalRate: Total room rate for ENTIRE stay (all nights combined) in plan_context currency.
- Always call search_hotels — do NOT make up hotel data
- For multi-segment: run separate searches per segment
- Choose hotels based on actual results, prioritizing: rating, location, price-to-value ratio
- Use the EXACT hotel name as it appears in search results
- check_in_time and check_out_time: Use the values from the search results
- Do NOT output final JSON until ALL segments have been searched
"""

# Fields the LLM needs to select a hotel; everything else is noise
_HOTEL_LLM_FIELDS = {"name", "gpsCoordinates", "nearbyPlaces", "hotelClass", "checkInTime", "ratePerNight","totalRate", "totalRate", "overallRating", "reviews", "amenities"}

def _slim_hotel_result(tool_result: Any) -> Any:
    """Strip heavy fields from hotel search results for LLM context.
    Full data is preserved in tool_logs for programmatic use."""
    if not isinstance(tool_result, dict):
        return tool_result
    # dotnet_client wraps response in {"success": ..., "data": <actual>}
    actual = tool_result.get("data", tool_result)
    if not isinstance(actual, dict):
        return tool_result
    properties = actual.get("properties") or actual.get("Properties")
    if not properties or not isinstance(properties, list):
        return tool_result
    slimmed = []
    for p in properties:
        slimmed.append({k: v for k, v in p.items() if k in _HOTEL_LLM_FIELDS})
    logger.info(f"   [HOTEL_AGENT] Slimmed {len(properties)} hotels: kept fields={_HOTEL_LLM_FIELDS}")
    return {"properties": slimmed}


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
            slim_tool_output=_slim_hotel_result,
        )
        hotel_result = _extract_json(result.content)
        hotel_result["tools"] = tool_logs
        
        # Mock - HN
        # hotel_result = _extract_json(HOTEL_AGENT_MOCK)

    except Exception as e:
        logger.error(f"   ❌ Hotel Agent error: {e}", exc_info=True)
        hotel_result = {"hotels_found": False, "error": str(e)}

    # --- Phase 2: Resolve hotel names to placeIds (parallel) ---
    if hotel_result.get("segments") and not hotel_result.get("error"):
        segments = hotel_result.get("segments", [])
        tool_logs = hotel_result.get("tools", [])

        # Build GPS lookup and full data lookup from tool_logs
        hotel_coords: dict[str, str] = {}
        hotel_data_dict: dict[str, dict] = {}
        for log in reversed(tool_logs):
            # dotnet_client wraps response in {"success": ..., "data": <actual>}
            raw_output = log.get("output") or {}
            actual_data = raw_output.get("data", raw_output) if isinstance(raw_output, dict) else raw_output
            if not isinstance(actual_data, dict):
                continue
            props = actual_data.get("properties") or actual_data.get("Properties") or []
            for p in props:
                name = p.get("name") or p.get("Name") or ""
                gps = p.get("gpsCoordinates") or p.get("GpsCoordinates") or {}
                lat = gps.get("latitude") or gps.get("Latitude")
                lng = gps.get("longitude") or gps.get("Longitude")
                if name and lat and lng:
                    hotel_coords[name] = f"{lat},{lng}"
                if name and name not in hotel_data_dict:
                    hotel_data_dict[name] = p

        # Assign link and alternatives per segment
        for seg in segments:
            hotel_name = seg.get("recommend_hotel_name", "")
            seg_data = hotel_data_dict.get(hotel_name, {})
            # Get link from the search result property
            seg["link"] = seg_data.get("link") or seg_data.get("Link") or ""
            
            # Find alternatives
            alternatives = []
            chosen_names = [s.get("recommend_hotel_name") for s in segments]
            for name, data in hotel_data_dict.items():
                if name != hotel_name and name not in chosen_names and len(alternatives) < 3:
                    # TotalRate from controller is already p.TotalRate?.Lowest (a string like "$111")
                    rate = data.get("totalRate") or data.get("TotalRate") or ""
                    rating = data.get("overallRating") or data.get("OverallRating") or 0
                    alt_link = data.get("link") or data.get("Link") or ""
                    hotel_class = data.get("hotelClass") or data.get("HotelClass") or ""
                    if rate and rating:
                        alternatives.append({
                            "name": name, 
                            "totalRate": rate, 
                            "overallRating": rating, 
                            "hotel_class": hotel_class,
                            "link": alt_link,
                        })
            seg["alternatives"] = alternatives

        async def _resolve_hotel(seg: dict) -> None:
            hotel_name = seg.get("recommend_hotel_name", "")
            if not hotel_name or seg.get("recommend_hotel_placeId"):
                return
            try:
                # Use precise GPS from search results, not broad city name
                location_bias = hotel_coords.get(hotel_name)
                logger.info(f"   🔍 Resolving hotel '{hotel_name}' with bias={location_bias}")
                resolved = await resolve_single_place(hotel_name, location_bias=location_bias)
                if resolved and resolved.get("placeId"):
                    seg["recommend_hotel_placeId"] = resolved["placeId"]
                    if "location" in resolved:
                        seg["_location"] = resolved["location"]
                    logger.info(f"   ✅ Hotel '{hotel_name}' → placeId={resolved['placeId']}")
            except Exception as e:
                logger.error(f"   ⚠️ Hotel resolve failed for '{hotel_name}': {e}")

        await asyncio.gather(*[_resolve_hotel(seg) for seg in segments])

    logger.info("🏨 [HOTEL_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"hotel_agent": hotel_result},
        "messages": [AIMessage(content=f"[Hotel Agent] Hotel search completed")],
    }
