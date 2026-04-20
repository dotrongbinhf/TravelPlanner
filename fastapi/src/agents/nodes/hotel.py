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
        model=settings.MODEL_NAME,
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model=settings.MODEL_NAME,
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_HOTEL or settings.GOOGLE_GEMINI_API_KEY,
        temperature=0.3,
        streaming=False,
    )
)

HOTEL_AGENT_SYSTEM = """You are the Hotel Agent for a travel planning system.

You find hotels using the search_hotels tool.

## Input
You receive:
1. **plan_context**: Shared trip info (destination, dates, passengers, budget, currency)
2. **mobility_plan**: Trip logistics — segments with hotel_search_area and hotel_nights
3. **task**: A concise description of what to search for — price preferences, children_ages, special notes

## How to determine hotel segments
Read `mobility_plan.segments`. For each segment that has `hotel_nights` (non-empty array):
- Use `hotel_search_area` as the search location
- Use `hotel_nights` (0-indexed night numbers) to calculate check-in and check-out dates from `start_date`
  - check_in = start_date + min(hotel_nights) days
  - check_out = start_date + max(hotel_nights) + 1 days
  - Example: start_date="2026-03-17", hotel_nights=[0,1,2] → check_in="2026-03-17", check_out="2026-03-20"

## Process
1. Read plan_context, mobility_plan, and task carefully
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

def _upgrade_image_url(url: str) -> str:
    """Upgrades Google thumbnail URLs to high quality size for UI rendering."""
    if not url:
        return ""
    if "=" in url and ("googleusercontent.com" in url or "ggpht.com" in url):
        return url.split("=")[0] + "=s800"
    return url


async def hotel_agent_node(state: GraphState) -> dict[str, Any]:
    """Hotel Agent Node — searches and selects hotels based on the mobility plan.
    Uses Google Hotels API (via .NET backend) per segment.
    """
    logger.info("=" * 60)
    logger.info("🏨 [HOTEL_AGENT] Node entered")

    plan = state.get("macro_plan", {})
    current_plan = state.get("current_plan", {})
    plan_context = current_plan.get("plan_context", {})
    mobility_plan = plan.get("mobility_plan", {})
    routed_intent = state.get("routed_intent", "")

    # Unified task request — from Orchestrator (pipeline) or Intent (standalone)
    agent_requests = plan.get("agent_requests", {})
    agent_request = agent_requests.get("hotel", "")

    if not agent_request:
        logger.info("   No agent_request for hotel → skip")
        return {
            "agent_outputs": {"hotel_agent": {"hotels_found": False, "skipped": True}},
            "messages": [AIMessage(content="[Hotel Agent] No hotel search needed")],
        }

    is_pipeline = routed_intent in ["full_plan", "draft_plan"]
    logger.info(f"   Mode: {'PIPELINE' if is_pipeline else 'STANDALONE'} (Intent: {routed_intent})")

    hotel_result = {}

    try:
        human_content = f"""Plan context:
{json.dumps(plan_context, indent=2, ensure_ascii=False)}

Mobility plan:
{json.dumps(mobility_plan, indent=2, ensure_ascii=False) if mobility_plan else "N/A"}

Task:
{agent_request}"""

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
            # Get link, thumbnail, and details for recommended hotel
            seg["link"] = seg_data.get("link") or seg_data.get("Link") or ""
            raw_thumb = seg_data.get("thumbnail") or seg_data.get("Thumbnail") or ""
            seg["thumbnail"] = _upgrade_image_url(raw_thumb)
            
            # totalRate might be an object or a string depending on API serialization
            rate_obj = seg_data.get("totalRate") or seg_data.get("TotalRate") or {}
            if isinstance(rate_obj, str):
                seg["totalRate"] = rate_obj
            elif isinstance(rate_obj, dict):
                seg["totalRate"] = rate_obj.get("lowest") or rate_obj.get("Lowest") or "N/A"
            else:
                seg["totalRate"] = "N/A"
            
            seg["overallRating"] = seg_data.get("overallRating") or seg_data.get("OverallRating") or "N/A"
            seg["reviews"] = seg_data.get("reviews") or seg_data.get("Reviews") or 0
            seg["hotel_class"] = seg_data.get("hotelClass") or seg_data.get("HotelClass") or "N/A"
            seg["checkInTime"] = seg_data.get("checkInTime") or seg_data.get("CheckInTime") or "N/A"
            seg["checkOutTime"] = seg_data.get("checkOutTime") or seg_data.get("CheckOutTime") or "N/A"

            # Find alternatives
            alternatives = []
            max_alts = 2 if is_pipeline else 4
            chosen_names = [s.get("recommend_hotel_name") for s in segments]
            for name, data in hotel_data_dict.items():
                if name != hotel_name and name not in chosen_names and len(alternatives) < max_alts:
                    rate_obj_alt = data.get("totalRate") or data.get("TotalRate") or {}
                    if isinstance(rate_obj_alt, str):
                        rate = rate_obj_alt
                    elif isinstance(rate_obj_alt, dict):
                        rate = rate_obj_alt.get("lowest") or rate_obj_alt.get("Lowest") or "N/A"
                    else:
                        rate = "N/A"
                    
                    rating = data.get("overallRating") or data.get("OverallRating") or "N/A"
                    reviews = data.get("reviews") or data.get("Reviews") or 0
                    alt_link = data.get("link") or data.get("Link") or ""
                    hotel_class = data.get("hotelClass") or data.get("HotelClass") or "N/A"
                    raw_alt_thumb = data.get("thumbnail") or data.get("Thumbnail") or ""
                    alt_thumb = _upgrade_image_url(raw_alt_thumb)
                    check_in = data.get("checkInTime") or data.get("CheckInTime") or "N/A"
                    check_out = data.get("checkOutTime") or data.get("CheckOutTime") or "N/A"
                    
                    alternatives.append({
                        "name": name, 
                        "totalRate": rate, 
                        "overallRating": rating,
                        "reviews": reviews,
                        "hotel_class": hotel_class,
                        "link": alt_link,
                        "thumbnail": alt_thumb,
                        "checkInTime": check_in,
                        "checkOutTime": check_out
                    })
            seg["alternatives"] = alternatives

        async def _resolve_hotel_item(item_dict: dict, name_key: str, pid_key: str) -> None:
            hotel_name = item_dict.get(name_key, "")
            if not hotel_name or item_dict.get(pid_key):
                return
            try:
                location_bias = hotel_coords.get(hotel_name)
                resolved = await resolve_single_place(hotel_name, location_bias=location_bias)
                if resolved and resolved.get("placeId"):
                    item_dict[pid_key] = resolved["placeId"]
                    if "location" in resolved:
                        item_dict["_location"] = resolved["location"]
            except Exception as e:
                logger.error(f"   ⚠️ Hotel resolve failed for '{hotel_name}': {e}")

        resolve_tasks = []
        for seg in segments:
            # Resolve the main recommendation
            resolve_tasks.append(_resolve_hotel_item(seg, "recommend_hotel_name", "recommend_hotel_placeId"))
            # Resolve all alternatives so they appear on the frontend map
            for alt in seg.get("alternatives", []):
                resolve_tasks.append(_resolve_hotel_item(alt, "name", "placeId"))

        if resolve_tasks:
            await asyncio.gather(*resolve_tasks)

    logger.info("🏨 [HOTEL_AGENT] Node completed")
    logger.info("=" * 60)

    # Strip raw tool logs from output to drastically reduce DB bloat
    if "tools" in hotel_result:
        hotel_result.pop("tools", None)

    return {
        "agent_outputs": {"hotel_agent": hotel_result},
        "messages": [AIMessage(content=f"[Hotel Agent] Hotel search completed")],
    }
