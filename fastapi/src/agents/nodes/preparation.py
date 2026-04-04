"""
Preparation Agent — Budget, Packing & Travel Notes.

Receives plan_context + weather + itinerary summary to generate:
1. Other costs budget mapped to predefined categories
2. Targeted packing lists based on weather + specific places
3. Practical travel notes with place-specific advice

Weather is fetched programmatically (code-controlled).
Itinerary summary extracted from itinerary_agent output for context-aware advice.

Runs in parallel with Restaurant Agent after Itinerary phase.
"""

import json
import logging
from datetime import datetime, date, timedelta
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.tools.dotnet_tools import get_weather_forecast
from src.tools.search_tools import tavily_search
from src.config import settings

logger = logging.getLogger(__name__)

llm_preparation = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)

PREPARATION_AGENT_SYSTEM = """You are the Preparation Agent for a travel planning system.

You handle: OTHER budget estimation, packing suggestions, and practical travel notes.

## Input
You receive:
1. Full trip plan_context (destination, dates, travelers, budget, travel mode, pace, mobility plan)
2. Daily weather forecast (pre-fetched, per-day temperature and conditions)
3. Itinerary summary (which places are visited each day — use this for transport cost estimation, place-specific packing advice, and practical notes)

## Budget — ONLY "Other" costs
You estimate NON-ITINERARY costs only. Do NOT include:
- ❌ Flight costs (handled by Flight Agent)
- ❌ Hotel/accommodation costs (handled by Hotel Agent)
- ❌ Attraction entry fees (handled by Attraction Agent)
- ❌ Restaurant/main meal costs (handled by Restaurant Agent)

## Budget Categories — MUST use these exact "type" values:
- "Food & Drinks" — snacks, coffee, drinks, street food BETWEEN main meals
- "Transport" — local transportation (taxi/Grab, bus, metro between attractions), or long-distance (departure to destination) transport if not flight
- "Activities" — minor entry fees, parking, bike rentals, boat rides, or activities not covered by Attraction Agent
- "Shopping" — souvenirs, gifts, local products
- "Other" — SIM card, internet, tips, contingency, any miscellaneous expenses
NOTE: Do NOT use "Accommodation" type — hotel costs are handled separately.

## Process
1. Review the weather data and itinerary summary provided
2. Optionally use tavily_search if you need specific travel tips for the destination
3. Based on itinerary places + weather → create practical packing list
   - Consider place-specific requirements (e.g., modest clothing for temples/mausoleums, sunscreen for outdoor attractions, water for long walks)
4. Estimate budget items based on itinerary (more places/farther apart → higher transport costs, hot weather → more drinks)
5. Write practical notes with place-specific advice

## Tools
### tavily_search
- ONLY search if the destination is genuinely unfamiliar or niche (e.g., a small town, remote area). For well-known cities (Hanoi, Da Nang, Bangkok, Tokyo, Paris...),if you already have sufficient knowledge or user don't have any specific requirements — DO NOT search.
- Queries must be short. You MAY append the current year for fresh results. Do NOT include trip details (ages, budget, dates) in queries.
  ✅ "Vietnam tipping culture 2026", "Grab taxi Hanoi", "Ha Giang road conditions 2026"
  ❌ "Hanoi travel tips for families with 8 year old", "best things to do in Hanoi April 2026 moderate budget"
- One topic per search call. Multiple calls allowed if truly needed.

## Response Format
CRITICAL: If your next step is to use a tool, return your response to call the tool. If you don't need to use tools anymore, your response must be one and ONLY one valid JSON object. No text before or after. Just the raw JSON starting with { and ending with }.
Respond in the language specified in the `language` field of the trip context (e.g., "vi" → Vietnamese, "en" → English). ALL text content (labels, details, titles, notes, weather_summary) MUST be in this language.

{
  "budget": {
    "currency": "VND",
    "breakdown": [
      {"type": "Transport", "name": "Grab/taxi between attractions", "amount": 600000, "details": "~100k/trip × 6 trips between spread-out sites"},
      {"type": "Transport", "name": "Airport transfer", "amount": 200000, "details": "Grab from Noi Bai to hotel ~200k"},
      {"type": "Food & Drinks", "name": "Street snacks & coffee", "amount": 300000, "details": "Egg coffee, street food between meals ~75k/day × 4 days"},
      {"type": "Food & Drinks", "name": "Bottled water", "amount": 100000, "details": "Water for hot outdoor days visiting temples"},
      {"type": "Shopping", "name": "Souvenirs & gifts", "amount": 500000, "details": "Local products, small gifts for entire trip"},
      {"type": "Activities", "name": "Bike rental at West Lake", "amount": 100000, "details": "2-hour rental"},
      {"type": "Other", "name": "Tourist SIM card", "amount": 100000, "details": "4G data SIM"},
      {"type": "Other", "name": "Contingency fund", "amount": 400000, "details": "Emergency/unexpected expenses over 4 days"}
    ]
  },
  "packing_lists": [
    {"name": "Essentials", "items": ["ID/Passport", "Phone charger", "Personal medication", "Cash & cards"]},
    {"name": "Clothing", "items": ["Light t-shirts", "Comfortable walking shoes", "Long pants/skirt for temple visits", "Light rain jacket"]},
    {"name": "Accessories", "items": ["Sunscreen (outdoor sites)", "Sunglasses", "Hat", "Umbrella", "Reusable water bottle"]}
  ],
  "notes": [
    {"title": "Transportation", "content": "Grab is widely available..."},
    {"title": "Dress code", "content": "Ho Chi Minh Mausoleum requires modest clothing — no shorts, tank tops, or short skirts..."},
    {"title": "Weather tips", "content": "April in Hanoi is hot and humid — bring water when walking around Hoan Kiem Lake..."},
    {"title": "Safety", "content": "Be careful when crossing streets in the Old Quarter..."}
  ],
  "weather_details": [
    {"day": 0, "date": "2026-04-03", "day_of_week": "Friday", "condition": "Partly cloudy", "temp_min": 24, "temp_max": 31, "humidity": 75, "rain_chance": 20},
    {"day": 1, "date": "2026-04-04", "day_of_week": "Saturday", "condition": "Light rain", "temp_min": 23, "temp_max": 29, "humidity": 85, "rain_chance": 70}
  ],
  "weather_summary": "Overall weather expected during the trip..."
}

## Rules
- Budget is ONLY for "other" costs — DO NOT include flight/hotel/restaurant/attraction
- Budget amounts are for the ENTIRE trip duration (all days combined), NOT per-day
- Budget "type" MUST be one of: "Food & Drinks", "Transport", "Activities", "Shopping", "Other"
- Multiple entries CAN share the same "type" — split by specific cost item (e.g., 2 separate "Transport" entries for taxi vs airport transfer)
- Use the itinerary to reason about transport costs (more stops/farther apart → higher cost)
- Use the itinerary to give place-specific packing and note advice
- Packing list should reflect ACTUAL weather forecast + specific places being visited
- Consider number of travelers, children/infants, pace, travel mode, and local transport
- Be practical and specific to the destination
- If weather data notes some days are outside forecast range, mention this in weather_summary
"""


# ============================================================================
# PROGRAMMATIC WEATHER FETCH
# ============================================================================

async def _fetch_weather_for_trip(
    destination: str,
    start_date_str: str,
    end_date_str: str,
) -> dict[str, Any]:
    """Fetch weather forecast programmatically and trim to trip dates.

    Returns per-day weather with simplified, LLM-friendly format.
    """
    today = date.today()

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        logger.warning("[weather] Invalid dates, using defaults")
        return {
            "daily": [],
            "covered_days": 0,
            "total_trip_days": 0,
            "outside_range_note": "Could not parse trip dates for weather forecast.",
        }

    total_trip_days = (end_date - start_date).days + 1
    days_until_end = (end_date - today).days + 1
    days_to_fetch = min(max(days_until_end, 1), 16)

    logger.info(
        f"[weather] Trip: {start_date_str} to {end_date_str} ({total_trip_days} days), "
        f"today={today}, fetching {days_to_fetch} days forecast"
    )

    # Call the weather API programmatically
    try:
        raw_result = await get_weather_forecast.ainvoke({
            "city": destination,
            "days": days_to_fetch,
        })
    except Exception as e:
        logger.error(f"[weather] API call failed: {e}")
        return {
            "daily": [],
            "covered_days": 0,
            "total_trip_days": total_trip_days,
            "outside_range_note": f"Weather API error: {str(e)}",
        }

    # Extract the forecast list
    # API returns: {success: true, status_code: 200, data: {list: [...], ...}}
    forecast_list = []
    if isinstance(raw_result, dict):
        inner = raw_result.get("data", raw_result)
        if isinstance(inner, dict):
            forecast_list = inner.get("list", inner.get("forecast", []))
        elif isinstance(inner, list):
            forecast_list = inner
        if not forecast_list:
            forecast_list = raw_result.get("list", [])
    elif isinstance(raw_result, list):
        forecast_list = raw_result

    logger.info(f"[weather] Raw forecast entries: {len(forecast_list)}")

    # Trim to trip dates and format per-day summary
    daily_weather = []
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for entry in forecast_list:
        entry_date = None

        if "dt" in entry:
            try:
                entry_date = datetime.fromtimestamp(entry["dt"]).date()
            except (ValueError, TypeError, OSError):
                pass
        elif "date" in entry:
            try:
                entry_date = datetime.strptime(str(entry["date"])[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        if not entry_date or not (start_date <= entry_date <= end_date):
            continue

        # Build simplified per-day weather
        day_idx = (entry_date - start_date).days
        temp = entry.get("temp", {})
        weather_list = entry.get("weather", [{}])
        condition = weather_list[0].get("description", "Unknown") if weather_list else "Unknown"

        day_weather = {
            "day": day_idx,
            "date": entry_date.isoformat(),
            "day_of_week": day_names[entry_date.weekday()],
            "condition": condition,
            "temp_min": temp.get("min", temp.get("night", 0)),
            "temp_max": temp.get("max", temp.get("day", 0)),
            "humidity": entry.get("humidity", 0),
        }

        # Add rain probability if available
        if "pop" in entry:
            day_weather["rain_chance_pct"] = round(entry["pop"] * 100)
        if entry.get("rain"):
            day_weather["rain_mm"] = entry["rain"]

        daily_weather.append(day_weather)

    # Check 16-day range limit
    outside_range_note = None
    max_forecast_date = today + timedelta(days=15)

    if start_date > max_forecast_date:
        outside_range_note = (
            f"All trip dates ({start_date_str} to {end_date_str}) are beyond the 16-day "
            f"forecast window (max {max_forecast_date.isoformat()}). "
            f"Weather data is based on historical/seasonal patterns for {destination}."
        )
    elif end_date > max_forecast_date:
        outside_range_note = (
            f"Weather forecast covers {start_date_str} to {max_forecast_date.isoformat()}. "
            f"Days after {max_forecast_date.isoformat()} are outside the 16-day forecast range."
        )

    result = {
        "daily": daily_weather,
        "covered_days": len(daily_weather),
        "total_trip_days": total_trip_days,
        "outside_range_note": outside_range_note,
    }

    logger.info(
        f"[weather] Result: {len(daily_weather)}/{total_trip_days} days covered, "
        f"outside_range={outside_range_note is not None}"
    )
    return result


# ============================================================================
# ITINERARY SUMMARY EXTRACTOR
# ============================================================================

def _extract_itinerary_summary(itinerary_data: dict) -> list[dict]:
    """Extract a simplified itinerary summary for the Preparation Agent.

    Shows day → list of place names with roles, including hotel (start/end day).
    """
    summary = []
    for day_data in itinerary_data.get("days", []):
        day_idx = day_data.get("day", 0)
        places = []
        for stop in day_data.get("stops", []):
            role = stop.get("role", "")
            name = stop.get("name", "")

            # Simplify hotel boundary roles
            if role in ("start_day", "end_day"):
                places.append({"name": name, "role": "hotel"})
            else:
                places.append({"name": name, "role": role})
        if places:
            summary.append({"day": day_idx, "stops": places})
    return summary


# ============================================================================
# AGENT NODE
# ============================================================================

async def preparation_agent_node(state: GraphState) -> dict[str, Any]:
    """Preparation Agent — Other budget, packing, notes.

    1. Fetches weather programmatically (code-controlled)
    2. Extracts simplified itinerary summary
    3. Passes weather + itinerary + plan_context to LLM
    4. LLM may optionally use Tavily for research
    5. Returns budget, packing, notes
    """
    logger.info("=" * 60)
    logger.info("🎒 [PREPARATION_AGENT] Node entered")

    plan = state.get("orchestrator_plan", {})
    plan_context = plan.get("plan_context", {})
    agent_outputs = state.get("agent_outputs", {})

    destination = plan_context.get("destination", "")
    if not destination:
        logger.info("   No destination → skip")
        return {
            "agent_outputs": {"preparation_agent": {"skipped": True}},
            "messages": [AIMessage(content="[Preparation Agent] No destination, skipping")],
        }

    preparation_result = {}

    try:
        # ── Step 1: Fetch weather programmatically ───────────────────
        logger.info("🎒 [PREPARATION_AGENT] Fetching weather...")
        weather_data = await _fetch_weather_for_trip(
            destination=destination,
            start_date_str=plan_context.get("start_date", ""),
            end_date_str=plan_context.get("end_date", ""),
        )

        # ── Step 2: Extract itinerary summary ────────────────────────
        itinerary_data = agent_outputs.get("itinerary_agent", {})
        itinerary_summary = _extract_itinerary_summary(itinerary_data)
        logger.info(f"🎒 [PREPARATION_AGENT] Itinerary: {len(itinerary_summary)} days extracted")

        # ── Step 3: Build context for LLM ────────────────────────────
        human_content = f"""## Trip Context
{json.dumps(plan_context, indent=2, ensure_ascii=False)}

## Daily Weather Forecast
{json.dumps(weather_data, indent=2, ensure_ascii=False)}

## Itinerary Summary (places per day)
{json.dumps(itinerary_summary, indent=2, ensure_ascii=False)}

Based on ALL the context above:
1. Estimate OTHER budget items (NOT flight/hotel/restaurant/attraction costs) — use exact type values: "Food & Drinks", "Transport", "Activities", "Shopping", "Other"
2. Create a packing list based on weather + specific places visited (e.g., temple dress codes, outdoor sun protection)
3. Write practical travel notes with place-specific advice for {destination}

You may use tavily_search if you need specific local tips or customs info."""

        llm_messages = [
            SystemMessage(content=PREPARATION_AGENT_SYSTEM),
            HumanMessage(content=human_content),
        ]

        # LLM may call Tavily if needed, otherwise returns JSON directly
        result, tool_logs = await _run_agent_with_tools(
            llm=llm_preparation, messages=llm_messages,
            tools=[tavily_search], max_iterations=3,
            agent_name="PREPARATION_AGENT",
        )
        preparation_result = _extract_json(result.content)
        preparation_result["tools"] = tool_logs
        preparation_result["weather_raw"] = weather_data

    except Exception as e:
        logger.error(f"   ❌ Preparation Agent error: {e}", exc_info=True)
        preparation_result = {"error": str(e)}

    logger.info("🎒 [PREPARATION_AGENT] Node completed")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"preparation_agent": preparation_result},
        "messages": [AIMessage(content="[Preparation Agent] Budget, packing, and notes prepared")],
    }
