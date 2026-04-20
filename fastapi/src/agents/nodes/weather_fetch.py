"""
Weather Fetch Node — Lightweight programmatic weather data retrieval.

Runs in parallel with Phase 1 agents (flight, hotel, attraction).
Stores weather data in agent_outputs["weather"] for downstream use by:
- Itinerary Agent (weather-aware scheduling)
- Preparation Agent (packing lists, weather notes)
"""

import logging
from datetime import datetime, date, timedelta
from typing import Any
from langchain_core.messages import AIMessage

from src.agents.state import GraphState
from src.tools.dotnet_tools import get_weather_forecast

logger = logging.getLogger(__name__)


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
        day_idx = (entry_date - start_date).days + 1
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
# AGENT NODE
# ============================================================================

async def weather_fetch_node(state: GraphState) -> dict[str, Any]:
    """Weather Fetch Node — Lightweight, no LLM.

    Fetches weather forecast and stores in agent_outputs for downstream agents.
    Runs in parallel with Phase 1 (flight, hotel, attraction).
    """
    logger.info("=" * 60)
    logger.info("🌤️ [WEATHER_FETCH] Node entered")

    plan = state.get("macro_plan", {})
    current_plan = state.get("current_plan", {})
    plan_context = current_plan.get("plan_context", {})

    destination = plan_context.get("destination", "")
    if not destination:
        logger.info("   No destination → skip")
        return {
            "agent_outputs": {"weather": {"daily": [], "skipped": True}},
            "messages": [AIMessage(content="[Weather] No destination, skipping")],
        }

    start_date_str = plan_context.get("start_date", "")
    end_date_str = plan_context.get("end_date", "")

    # If no start_date, we can't fetch weather forecast
    if not start_date_str:
        logger.info("   No start_date → skip weather (no specific dates)")
        return {
            "agent_outputs": {"weather": {"daily": [], "skipped": True,
                "outside_range_note": "No specific dates provided — cannot fetch weather forecast."}},
            "messages": [AIMessage(content="[Weather] No dates, skipping")],
        }

    # Fallback: compute end_date from start_date + num_days if missing
    if not end_date_str:
        num_days = plan_context.get("num_days")
        if num_days:
            from datetime import datetime, timedelta
            try:
                sd = datetime.strptime(start_date_str, "%Y-%m-%d")
                ed = sd + timedelta(days=int(num_days) - 1)
                end_date_str = ed.strftime("%Y-%m-%d")
                logger.info(f"   Auto-computed end_date for weather: {end_date_str}")
            except (ValueError, TypeError):
                pass
        if not end_date_str:
            logger.info("   No end_date and no num_days → skip weather")
            return {
                "agent_outputs": {"weather": {"daily": [], "skipped": True,
                    "outside_range_note": "Missing end_date — cannot determine trip duration."}},
                "messages": [AIMessage(content="[Weather] No end_date, skipping")],
            }

    weather_data = await _fetch_weather_for_trip(
        destination=destination,
        start_date_str=start_date_str,
        end_date_str=end_date_str,
    )

    covered = weather_data.get("covered_days", 0)
    total = weather_data.get("total_trip_days", 0)
    logger.info(f"🌤️ [WEATHER_FETCH] Completed: {covered}/{total} days covered")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"weather": weather_data},
        "messages": [AIMessage(content=f"[Weather] Fetched forecast: {covered}/{total} days")],
    }
