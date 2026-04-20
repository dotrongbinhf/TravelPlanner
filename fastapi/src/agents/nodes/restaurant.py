"""
Restaurant Agent — 3-Phase Pipeline.

Phase 1: LLM generates a diverse meal plan with search queries per meal
Phase 2: Code runs Text Search programmatically (concurrent, with fallback chain)
Phase 3: LLM selects the best restaurant per meal from search results

All API calls are code-controlled — the LLM NEVER calls tools directly.
"""

import json
import asyncio
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json
from src.tools.maps_tools import search_restaurants_for_meal, places_text_search_full
from src.config import settings

logger = logging.getLogger(__name__)

USE_ENTERPRISE_FIELDS = settings.USE_ENTERPRISE_FIELDS

llm_restaurant = (
    ChatOpenAI(
        model=settings.MODEL_NAME,
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_RESTAURANT or settings.GOOGLE_GEMINI_API_KEY,
        temperature=0.3,
        streaming=False,
    )
)

# ============================================================================
# PHASE 1: LLM Meal Planning
# ============================================================================

MEAL_PLAN_SYSTEM = """You are a meal planning specialist for travelers.

Given the trip destination, traveler food preferences, dietary restrictions, and meal slots
extracted from an itinerary, create a diverse and appropriate meal plan.

For each meal slot, generate a suitable Text Search query to find restaurants on Google Maps.

## Rules
- Queries should be cuisine/restaurant TYPE (e.g., "Vietnamese traditional restaurant", "Seafood restaurant", "Pho restaurant")
- Do NOT include location names, landmarks, or "near X" in the query. The system already searches nearby the relevant location automatically.
- Ensure VARIETY across days — don't repeat the same cuisine type for every meal
- Queries can repeat the same cuisine type but on DIFFERENT days
- Some meals can simply use "restaurant" if no strong preference applies
- Consider the user's stated preferences, but add variety beyond just those
- The query language should be in the local language of the destination or English — whichever is more likely to return good Google Maps results
- Respond in the language specified in the `language` field (e.g., "vi" → Vietnamese, "en" → English)

## Response Format
Return ONLY a JSON array of meal plan entries. No text before or after.

[
  { "day": 1, "meal_type": "lunch", "query": "Pho restaurant" },
  { "day": 1, "meal_type": "dinner", "query": "Vietnamese traditional restaurant" },
  { "day": 2, "meal_type": "lunch", "query": "Bun Cha restaurant" },
  { "day": 2, "meal_type": "dinner", "query": "Seafood restaurant" },
  { "day": 3, "meal_type": "lunch", "query": "restaurant" }
]
"""


# ============================================================================
# PHASE 3: LLM Restaurant Selection
# ============================================================================

SELECTION_SYSTEM = """You are a restaurant selection specialist for travelers.

Given search results for each meal in a trip, select the BEST restaurant per meal.

## Rules
- Each meal entry includes `date` and `day_of_week` — use these to CHECK opening_hours
- If a restaurant's opening_hours show it is CLOSED on that day_of_week, do NOT select it
- **IMPORTANT**: If a meal has NO search_results (empty input array), you MUST still output a meal entry for it to estimate its cost. For such meals, set `name` to "Eat independently" (or equivalent in requested language), leave `place_id` empty, and provide a generic `note` about eating independently.
- Whether results exist or not, always output a reasonable `estimated_cost_total` for the meal.
- Choose restaurants that match the travelers' preferences and budget
- Do NOT select the same restaurant for different meals (choose variety)
- Estimate total meal cost for the ENTIRE group (all adults + children)
- Provide a brief note explaining your choice and describing the restaurant/food in the requested language.
- Do NOT include an `alternatives` field. The system will auto-fill alternatives from remaining search results.
- Respond in the language specified in the `language` field (e.g., "vi" → Vietnamese, "en" → English). The `note` field MUST be in this language.

## Response Format
Return ONLY a JSON array. No text before or after.

[
  {
    "day": 1,
    "meal_type": "lunch",
    "name": "Phở Thìn Bờ Hồ",
    "place_id": "ChIJ...",
    "estimated_cost_total": 180000,
    "note": "Famous Pho Restaurant, rating 4.5"
  }
]
"""

# ============================================================================
# MEAL SLOT PARSER
# ============================================================================

def _parse_meal_slots(itinerary_data: dict, resolved_places: dict) -> list[dict]:
    """Parse meal slots from itinerary output.

    For each lunch/dinner in the schedule, extract the day, meal_type,
    and the lat/lng of the nearest attraction BEFORE the meal.

    If the stop right before the meal is 'generic' (no real coords),
    uses the attraction before that.

    Args:
        itinerary_data: The itinerary agent output with 'days' array
        resolved_places: The resolved_places dict from itinerary pipeline
                         containing {airports: [...], hotels: [...], attractions: [...]}

    Returns:
        List of meal slot dicts with day, meal_type, near_attraction, lat, lng
    """
    # Build name→coords lookup from resolved_places
    coords_lookup: dict[str, tuple[float, float]] = {}
    for group_name in ["airports", "hotels", "attractions"]:
        for item in resolved_places.get(group_name, []):
            resolved = item.get("resolved")
            if not resolved:
                continue
            title = resolved.get("title", "")
            location = resolved.get("location", {})
            coordinates = location.get("coordinates", [])
            if title and len(coordinates) >= 2:
                # GeoJSON: [lng, lat]
                coords_lookup[title] = (coordinates[1], coordinates[0])

    meal_slots = []
    for day_data in itinerary_data.get("days", []):
        day_idx = day_data.get("day", 1)
        stops = day_data.get("stops", [])

        for i, stop in enumerate(stops):
            roles = stop.get("role", stop.get("roles", []))
            # Support both string and list just in case
            if isinstance(roles, str):
                roles = [roles]
            
            meal_type = None
            if "lunch" in roles:
                meal_type = "lunch"
            elif "dinner" in roles:
                meal_type = "dinner"
            
            if not meal_type:
                continue

            # Find the nearest attraction/real-place BEFORE or AFTER this meal
            near_attraction = ""
            lat, lng = 0.0, 0.0

            def _get_valid_location(idx: int) -> tuple[str, float, float]:
                if 0 <= idx < len(stops):
                    s = stops[idx]
                    s_roles = s.get("role", s.get("roles", []))
                    if isinstance(s_roles, str):
                        s_roles = [s_roles]
                    s_name = s.get("name", "")
                    
                    if "generic" not in s_roles and s_name in coords_lookup:
                        lat_val, lng_val = coords_lookup[s_name]
                        return s_name, lat_val, lng_val
                return "", 0.0, 0.0

            # 1. Check previous stop (i - 1)
            # If it's generic (or invalid), _get_valid_location returns empty
            prev_name, p_lat, p_lng = _get_valid_location(i - 1)
            
            if prev_name:
                near_attraction, lat, lng = prev_name, p_lat, p_lng
            else:
                # 2. If previous was generic (or no valid coords), check next stop (i + 1)
                next_name, n_lat, n_lng = _get_valid_location(i + 1)
                if next_name:
                    near_attraction, lat, lng = next_name, n_lat, n_lng
            
            # If both were generic (or not found), lat/lng remain 0.0 and it will be skipped later

            meal_slots.append({
                "day": day_idx,
                "meal_type": meal_type,
                "near_attraction": near_attraction,
                "lat": lat,
                "lng": lng,
            })

    return meal_slots


# ============================================================================
# AGENT NODE
# ============================================================================

async def restaurant_agent_node(state: GraphState) -> dict[str, Any]:
    """Restaurant Agent — 3-Phase Pipeline. Runs after Itinerary Agent.

    Phase 1: LLM generates meal plan with search queries
    Phase 2: Code runs Text Search concurrently for all meals
    Phase 3: LLM selects best restaurant per meal
    """
    logger.info("=" * 60)
    logger.info("🍽️ [RESTAURANT_AGENT] Node entered")

    plan = state.get("macro_plan", {})
    current_plan = state.get("current_plan", {})
    agent_outputs = state.get("agent_outputs", {})
    plan_context = current_plan.get("plan_context", {})

    # Unified task request — from Orchestrator (pipeline) or Intent (standalone)
    agent_requests = plan.get("agent_requests", {})
    agent_request = agent_requests.get("restaurant", "")

    if not agent_request:
        logger.info("   No agent_request for restaurant → skip")
        return {
            "agent_outputs": {"restaurant_agent": {"meals": [], "skipped": True}},
            "messages": [AIMessage(content="[Restaurant Agent] No restaurant search needed")],
        }

    is_pipeline = bool(plan.get("task_list"))
    logger.info(f"   Mode: {'PIPELINE' if is_pipeline else 'STANDALONE'}")

    # Get itinerary data — from pipeline agent_outputs or current_plan (standalone)
    itinerary_data = agent_outputs.get("itinerary_agent", {})
    if not itinerary_data or itinerary_data.get("error"):
        itinerary_data = current_plan.get("itinerary", {})

    if not itinerary_data or itinerary_data.get("error"):
        if is_pipeline:
            logger.info("   No valid itinerary data → skip (pipeline)")
            return {
                "agent_outputs": {"restaurant_agent": {"meals": [], "skipped": True, "reason": "no_itinerary"}},
                "messages": [AIMessage(content="[Restaurant Agent] No itinerary available, skipping")],
            }
        else:
            logger.info("   No itinerary data → Standalone Area Search mode")
            meal_slots = [{
                "day": 1,
                "meal_type": "standalone",
                "near_attraction": "",
                "lat": 0.0,
                "lng": 0.0,
            }]
    else:
        # ── Parse meal slots from itinerary ──────────────────────────
        resolved_places = itinerary_data.get("resolved_places", {})
        meal_slots = _parse_meal_slots(itinerary_data, resolved_places)
        logger.info(f"   Parsed {len(meal_slots)} meal slots from itinerary")

        if not meal_slots:
            logger.info("   No meal slots found → skip")
            return {
                "agent_outputs": {"restaurant_agent": {"meals": [], "skipped": True, "reason": "no_meals"}},
                "messages": [AIMessage(content="[Restaurant Agent] No meal slots in itinerary")],
            }

    restaurant_result = {}

    try:
        # ══════════════════════════════════════════════════════════════
        # PHASE 1: LLM Meal Planning
        # ══════════════════════════════════════════════════════════════
        logger.info("🍽️ [RESTAURANT_AGENT] Phase 1: LLM Meal Planning...")

        meal_slots_summary = [
            {"day": m["day"], "meal_type": m["meal_type"], "near_attraction": m["near_attraction"]}
            for m in meal_slots
        ]

        language = plan_context.get("language", "en")

        phase1_input = {
            "destination": plan_context.get("destination", ""),
            "num_days": plan_context.get("num_days", 1),
            "language": language,
            "budget_level": plan_context.get("budget_level", "moderate"),
            "task": agent_request,
            "meal_slots": meal_slots_summary,
        }

        phase1_messages = [
            SystemMessage(content=MEAL_PLAN_SYSTEM),
            HumanMessage(content=json.dumps(phase1_input, indent=2, ensure_ascii=False)),
        ]

        phase1_result = await llm_restaurant.ainvoke(phase1_messages)
        meal_plan = _extract_json(phase1_result.content)

        if not isinstance(meal_plan, list):
            meal_plan = meal_plan.get("meal_plan", []) if isinstance(meal_plan, dict) else []

        logger.info(f"   Phase 1: Generated {len(meal_plan)} meal queries")
        for mp in meal_plan:
            logger.info(f"     Day {mp.get('day')} {mp.get('meal_type')}: query='{mp.get('query')}'")

        # ══════════════════════════════════════════════════════════════
        # PHASE 2: Programmatic Search (concurrent)
        # ══════════════════════════════════════════════════════════════
        logger.info("🍽️ [RESTAURANT_AGENT] Phase 2: Programmatic Search...")

        # Map meal_plan queries to meal_slots (with lat/lng)
        search_tasks = []
        search_meal_info = []

        # Check if we're in standalone mode (no itinerary coordinates)
        is_standalone_search = any(s.get("meal_type") == "standalone" for s in meal_slots)

        for planned_meal in meal_plan:
            day = planned_meal.get("day", 1)
            meal_type = planned_meal.get("meal_type", "")
            query = planned_meal.get("query", "restaurant")

            if is_standalone_search:
                # Standalone Area Search — no coordinates available, use text search
                search_query = f"{query} in {plan_context.get('destination', '')}"
                search_tasks.append(
                    places_text_search_full.ainvoke({
                        "query": search_query,
                        "USE_ENTERPRISE_FIELDS": USE_ENTERPRISE_FIELDS,
                        "page_size": 5,
                    })
                )
                search_meal_info.append({
                    "day": day,
                    "meal_type": meal_type,
                    "query": query,
                    "near_attraction": "",
                })
            else:
                # Pipeline/Normal — match meal_plan to itinerary slots with lat/lng
                matching_slot = None
                for slot in meal_slots:
                    if slot["day"] == day and slot["meal_type"] == meal_type:
                        matching_slot = slot
                        break

                if not matching_slot:
                    logger.warning(f"   No slot for Day {day} {meal_type}, skipping search")
                    continue

                if matching_slot["lat"] == 0 and matching_slot["lng"] == 0:
                    # Slot exists but no coords — fallback to area search
                    search_query = f"{query} in {plan_context.get('destination', '')}"
                    search_tasks.append(
                        places_text_search_full.ainvoke({
                            "query": search_query,
                            "USE_ENTERPRISE_FIELDS": USE_ENTERPRISE_FIELDS,
                            "page_size": 5,
                        })
                    )
                else:
                    # Normal Nearby Search with coordinates
                    search_tasks.append(
                        search_restaurants_for_meal.ainvoke({
                            "query": query,
                            "lat": matching_slot["lat"],
                            "lng": matching_slot["lng"],
                            "USE_ENTERPRISE_FIELDS": USE_ENTERPRISE_FIELDS,
                            "page_size": 5,
                        })
                    )
                search_meal_info.append({
                    "day": day,
                    "meal_type": meal_type,
                    "query": query,
                    "near_attraction": matching_slot.get("near_attraction", ""),
                })

        # Run all searches concurrently
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Pair results with meal info
        meal_search_results = []
        for info, results in zip(search_meal_info, search_results):
            if isinstance(results, Exception):
                logger.error(f"   Search error for Day {info['day']} {info['meal_type']}: {results}")
                results = []

            meal_search_results.append({
                **info,
                "search_results": results,
            })
            logger.info(
                f"   Day {info['day']} {info['meal_type']}: "
                f"{len(results)} results for '{info['query']}'"
            )

        # ══════════════════════════════════════════════════════════════
        # PHASE 3: LLM Selection
        # ══════════════════════════════════════════════════════════════
        logger.info("🍽️ [RESTAURANT_AGENT] Phase 3: LLM Selection...")

        # Filter out meals with no results and trim search data for LLM
        # Compute date ↔ day_of_week mapping so LLM can check opening hours
        from datetime import datetime as dt, timedelta
        start_date_str = plan_context.get("start_date", "")
        try:
            trip_start = dt.strptime(start_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            trip_start = None

        meals_with_results = []
        for m in meal_search_results:
            # Trim each restaurant to only fields LLM needs for selection
            trimmed_results = []
            for r in m["search_results"]:
                trimmed = {
                    "name": r.get("name", ""),
                    "place_id": r.get("place_id", ""),
                    "address": r.get("address", ""),
                }
                if "rating" in r:
                    trimmed["rating"] = r["rating"]
                if "user_ratings_total" in r:
                    trimmed["user_ratings_total"] = r["user_ratings_total"]
                if "price_level" in r:
                    trimmed["price_level"] = r["price_level"]
                if "opening_hours" in r:
                    trimmed["opening_hours"] = r["opening_hours"]
                trimmed_results.append(trimmed)

            # Compute actual date and day of week for this meal's day index
            meal_entry = {
                "day": m["day"],
                "meal_type": m["meal_type"],
                "query": m["query"],
                "near_attraction": m.get("near_attraction", ""),
                "search_results": trimmed_results,
            }
            if trip_start:
                meal_date = trip_start + timedelta(days=m["day"] - 1)
                meal_entry["date"] = meal_date.isoformat()
                meal_entry["day_of_week"] = meal_date.strftime("%A")

            meals_with_results.append(meal_entry)

        if not meals_with_results:
            logger.warning("   No search results for any meal")
            restaurant_result = {"meals": [], "note": "No restaurants found near any meal locations"}
        else:
            phase3_input = {
                "destination": plan_context.get("destination", ""),
                "start_date": start_date_str,
                "language": language,
                "budget_level": plan_context.get("budget_level", "moderate"),
                "currency": plan_context.get("currency", "VND"),
                "adults": plan_context.get("adults", 2),
                "children": plan_context.get("children", 0),
                "task": agent_request,
                "meals": meals_with_results,
            }

            phase3_messages = [
                SystemMessage(content=SELECTION_SYSTEM),
                HumanMessage(content=json.dumps(phase3_input, indent=2, ensure_ascii=False)),
            ]

            phase3_result = await llm_restaurant.ainvoke(phase3_messages)
            selected_meals = _extract_json(phase3_result.content)

            if not isinstance(selected_meals, list):
                selected_meals = selected_meals.get("meals", []) if isinstance(selected_meals, dict) else []

            # Re-inject coordinates from original search results for map rendering
            placeid_to_location = {}
            placeid_to_result = {}  # full search result lookup for auto-filling alternatives
            for m in meal_search_results:
                for r in m.get("search_results", []):
                    pid = r.get("place_id")
                    if pid:
                        placeid_to_location[pid] = {"lat": r.get("lat", 0), "lng": r.get("lng", 0)}
                        placeid_to_result[pid] = r
            
            # Auto-fill alternatives from remaining search results + inject location
            for meal in selected_meals:
                pid = meal.get("place_id")
                if pid and pid in placeid_to_location:
                    loc = placeid_to_location[pid]
                    meal["_location"] = {"coordinates": [loc["lng"], loc["lat"]]}
                
                # Auto-fill alternatives from remaining search results for this meal
                if not meal.get("alternatives"):
                    meal_day = meal.get("day")
                    meal_type = meal.get("meal_type")
                    meal_sr = next(
                        (m for m in meal_search_results
                         if m["day"] == meal_day and m["meal_type"] == meal_type),
                        None
                    )
                    if meal_sr:
                        alts = []
                        for r in meal_sr.get("search_results", []):
                            r_pid = r.get("place_id")
                            if r_pid and r_pid != pid:
                                alts.append({
                                    "name": r.get("name", ""),
                                    "place_id": r_pid,
                                    "rating": r.get("rating"),
                                    "user_ratings_total": r.get("user_ratings_total"),
                                    "price_level": r.get("price_level"),
                                })
                            if len(alts) >= 4:
                                break
                        meal["alternatives"] = alts

            # --- Phase 3.5: Fetch Rich Data (Images, etc) from DB ---
            logger.info("🍽️ [RESTAURANT_AGENT] Phase 3.5: Fetching rich DB data...")
            from src.tools.dotnet_tools import get_place_from_db

            async def _enrich_w_db(item: dict):
                pid = item.get("place_id")
                if not pid:
                    return
                try:
                    result = await get_place_from_db.ainvoke({"place_id": pid})
                    if isinstance(result, dict) and result.get("success"):
                        item["db_data"] = result.get("data", {})
                except Exception as e:
                    logger.error(f"Failed to fetch db_data for restaurant {item.get('name')} (place_id: {pid}): {e}")

            enrich_tasks = []
            for meal in selected_meals:
                enrich_tasks.append(_enrich_w_db(meal))  # Always enrich recommended
                if is_standalone_search:
                    # Standalone: enrich alternatives too (for rich UI)
                    for alt in meal.get("alternatives", []):
                        if isinstance(alt, dict):
                            enrich_tasks.append(_enrich_w_db(alt))

            if enrich_tasks:
                await asyncio.gather(*enrich_tasks, return_exceptions=True)

            if not selected_meals:
                restaurant_result = {"meals": [], "note": "Failed to extract selection"}
            else:
                restaurant_result = {"meals": selected_meals}

        logger.info(f"   Phase 3: Selected {len(restaurant_result.get('meals', []))} restaurants")

    except Exception as e:
        logger.error(f"   ❌ Restaurant Agent error: {e}", exc_info=True)
        restaurant_result = {"error": str(e), "meals": []}

    num_meals = len(restaurant_result.get("meals", []))
    logger.info(f"🍽️ [RESTAURANT_AGENT] Completed: {num_meals} meals matched")
    logger.info("=" * 60)

    if "tools" in restaurant_result:
        restaurant_result.pop("tools", None)

    return {
        "agent_outputs": {"restaurant_agent": restaurant_result},
        "messages": [AIMessage(content=f"[Restaurant Agent] Found restaurants for {num_meals} meals")],
    }
