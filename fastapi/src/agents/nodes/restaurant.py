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

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json
from src.tools.maps_tools import search_restaurants_for_meal
from src.config import settings

logger = logging.getLogger(__name__)

llm_restaurant = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)

# ============================================================================
# PHASE 1: LLM Meal Planning
# ============================================================================

MOCK_MEAL_PLAN = [
  {
    "day": 0,
    "meal_type": "lunch",
    "query": "nhà hàng bún chả truyền thống"
  },
  {
    "day": 0,
    "meal_type": "dinner",
    "query": "nhà hàng món ăn Việt Nam gia đình"
  },
  {
    "day": 1,
    "meal_type": "lunch",
    "query": "nhà hàng phở ngon"
  },
  {
    "day": 1,
    "meal_type": "dinner",
    "query": "nhà hàng đặc sản Hà Nội"
  },
  {
    "day": 2,
    "meal_type": "lunch",
    "query": "nhà hàng cơm niêu Việt Nam"
  },
  {
    "day": 2,
    "meal_type": "dinner",
    "query": "quán ăn đường phố Hà Nội"
  },
  {
    "day": 3,
    "meal_type": "lunch",
    "query": "nhà hàng bánh cuốn truyền thống"
  }
]

MEAL_PLAN_SYSTEM = """You are a meal planning specialist for travelers.

Given the trip destination, traveler food preferences, dietary restrictions, and meal slots
extracted from an itinerary, create a diverse and appropriate meal plan.

For each meal slot, generate a suitable Text Search query to find restaurants on Google Maps.

## Rules
- Queries should be cuisine/restaurant TYPE (e.g., "Vietnamese traditional restaurant", "Seafood restaurant", "Pho restaurant")
- Ensure VARIETY across days — don't repeat the same cuisine type for every meal
- Queries can repeat the same cuisine type but on DIFFERENT days
- Some meals can simply use "restaurant" if no strong preference applies
- Consider the user's stated preferences, but add variety beyond just those
- The query language should be in the local language of the destination or English — whichever is more likely to return good Google Maps results
- Respond in the language specified in the `language` field (e.g., "vi" → Vietnamese, "en" → English)

## Response Format
Return ONLY a JSON array of meal plan entries. No text before or after.

[
  { "day": 0, "meal_type": "lunch", "query": "Vietnamese Pho restaurant" },
  { "day": 0, "meal_type": "dinner", "query": "Vietnamese traditional restaurant" },
  { "day": 1, "meal_type": "lunch", "query": "Bun Cha restaurant" },
  { "day": 1, "meal_type": "dinner", "query": "Seafood restaurant" },
  { "day": 2, "meal_type": "lunch", "query": "restaurant" }
]
"""


# ============================================================================
# PHASE 3: LLM Restaurant Selection
# ============================================================================
MOCK_SELECTION = [
  {
    "day": 0,
    "meal_type": "lunch",
    "name": "Bún Chả Que Tre",
    "place_id": "ChIJU3LMMUOrNTERaL170xOiY3M",
    "estimated_cost_total": 250000,
    "note": "Quán bún chả nổi tiếng, không gian phù hợp gia đình, đánh giá cao với 744 lượt bình chọn.",
    "alternatives": ["Tuyết Bún Chả - 104 Trần Nhật Duật", "Hùng - Bún Chả Gia Truyền"]
  },
  {
    "day": 0,
    "meal_type": "dinner",
    "name": "Góc Bếp Hà Thành",
    "place_id": "ChIJX9_lMwCrNTERm_ymoTKS8go",
    "estimated_cost_total": 600000,
    "note": "Nhà hàng chuyên món Việt với không gian ấm cúng, rất phù hợp cho bữa tối gia đình.",
    "alternatives": ["Épices d'Indochine Restaurant - Nhà hàng Gia Vị Đông Dương", "Nhà hàng Bắc Đỉnh"]
  },
  {
    "day": 1,
    "meal_type": "lunch",
    "name": "Phở bò Cô Hoa",
    "place_id": "ChIJq-sX-aerNTERFPF3qifBlqY",
    "estimated_cost_total": 180000,
    "note": "Phở truyền thống với hương vị chuẩn Hà Nội, được đánh giá rất cao về chất lượng nước dùng.",
    "alternatives": ["Phở Gia Thành", "Phở Gà Nguyệt"]
  },
  {
    "day": 1,
    "meal_type": "dinner",
    "name": "Mộng Mer - Đặc sản Huế",
    "place_id": "ChIJJ35t-G-rNTERGdN-EYvJxAc",
    "estimated_cost_total": 500000,
    "note": "Trải nghiệm ẩm thực đặc sản đa dạng, không gian sạch sẽ và phục vụ chuyên nghiệp.",
    "alternatives": ["Quan An Ngon", "Ngon Garden"]
  },
  {
    "day": 2,
    "meal_type": "lunch",
    "name": "Ẩm Thực Niêu Quán",
    "place_id": "ChIJtb_5fgCrNTER-3SBt4RVJN8",
    "estimated_cost_total": 450000,
    "note": "Cơm niêu truyền thống Việt Nam, không gian rộng rãi, rất thích hợp cho gia đình có trẻ nhỏ.",
    "alternatives": ["Niêu Quán", "Cơm niêu Singapore KOMBO - 30 Nguyễn Phong Sắc"]
  },
  {
    "day": 2,
    "meal_type": "dinner",
    "name": "Quán Ngon Phố Cổ",
    "place_id": "ChIJaefUR7-rNTERxsCI70VAJ4w",
    "estimated_cost_total": 400000,
    "note": "Nằm ngay khu phố cổ, phục vụ nhiều món ăn đường phố đặc trưng trong không gian thoải mái.",
    "alternatives": ["Quan An Ngon"]
  },
  {
    "day": 3,
    "meal_type": "lunch",
    "name": "Bánh Cuốn Gia Truyền Thanh Vân",
    "place_id": "ChIJ_cJfr76rNTERk1CbU0guunY",
    "estimated_cost_total": 200000,
    "note": "Thương hiệu bánh cuốn gia truyền lâu đời, hương vị tinh tế, là lựa chọn tuyệt vời cho bữa trưa.",
    "alternatives": ["Tuệ An | Bánh Cuốn Nóng & Phở Bò Bảo Khánh", "Bánh cuốn gia truyền Thanh Vân"]
  }
]

SELECTION_SYSTEM = """You are a restaurant selection specialist for travelers.

Given search results for each meal in a trip, select the best restaurant per meal.

## Rules
- Each meal entry includes `date` and `day_of_week` — use these to CHECK opening_hours
- If a restaurant's opening_hours show it is CLOSED on that day_of_week, do NOT select it
- Choose restaurants that match the travelers' preferences and budget
- Do NOT select the same restaurant for different meals (choose variety)
- Estimate total meal cost for the ENTIRE group (all adults + children)
- Provide a brief note explaining your choice
- Pick 2 alternatives from the remaining results (also must be open on that day)
- Respond in the language specified in the `language` field (e.g., "vi" → Vietnamese, "en" → English). The `note` field MUST be in this language.

## Response Format
Return ONLY a JSON array. No text before or after.

[
  {
    "day": 0,
    "meal_type": "lunch",
    "name": "Phở Thìn Bờ Hồ",
    "place_id": "ChIJ...",
    "estimated_cost_total": 180000,
    "note": "Famous Pho Restaurant, near Văn Miếu, rating 4.5",
    "alternatives": ["Phở Bát Đàn", "Phở 10 Lý Quốc Sư"]
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
        day_idx = day_data.get("day", 0)
        stops = day_data.get("stops", [])

        for i, stop in enumerate(stops):
            role = stop.get("role", "")
            if role not in ("lunch", "dinner"):
                continue

            # Find the nearest attraction/real-place BEFORE this meal
            near_attraction = ""
            lat, lng = 0.0, 0.0

            # Walk backwards from the meal stop
            for j in range(i - 1, -1, -1):
                prev_stop = stops[j]
                prev_role = prev_stop.get("role", "")
                prev_name = prev_stop.get("name", "")

                # Skip generic stops (no real coords)
                if prev_role == "generic":
                    continue

                # Try to find coords in lookup
                if prev_name in coords_lookup:
                    near_attraction = prev_name
                    lat, lng = coords_lookup[prev_name]
                    break

            meal_slots.append({
                "day": day_idx,
                "meal_type": role,
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
    logger.info("🍽️ [RESTAURANT_AGENT] Node entered (Phase 2)")

    plan = state.get("orchestrator_plan", {})
    plan_context = plan.get("plan_context", {})
    restaurant_ctx = plan.get("restaurant", {})
    agent_outputs = state.get("agent_outputs", {})
    itinerary_data = agent_outputs.get("itinerary_agent", {})

    if not restaurant_ctx:
        logger.info("   No restaurant context → skip")
        return {
            "agent_outputs": {"restaurant_agent": {"meals": [], "skipped": True}},
            "messages": [AIMessage(content="[Restaurant Agent] No restaurant search needed")],
        }

    if not itinerary_data or itinerary_data.get("error"):
        logger.info("   No valid itinerary data → skip")
        return {
            "agent_outputs": {"restaurant_agent": {"meals": [], "skipped": True, "reason": "no_itinerary"}},
            "messages": [AIMessage(content="[Restaurant Agent] No itinerary available, skipping")],
        }

    restaurant_result = {}

    try:
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
            "user_cuisine_preferences": restaurant_ctx.get("user_cuisine_preferences", []),
            "user_dietary_restrictions": restaurant_ctx.get("user_dietary_restrictions", []),
            "budget_level": plan_context.get("budget_level", "moderate"),
            "notes": restaurant_ctx.get("notes", ""),
            "meal_slots": meal_slots_summary,
        }

        phase1_messages = [
            SystemMessage(content=MEAL_PLAN_SYSTEM),
            HumanMessage(content=json.dumps(phase1_input, indent=2, ensure_ascii=False)),
        ]

        phase1_result = await llm_restaurant.ainvoke(phase1_messages)
        meal_plan = _extract_json(phase1_result.content)
        # meal_plan = MOCK_MEAL_PLAN

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

        # Comment to test
        for planned_meal in meal_plan:
            day = planned_meal.get("day", 0)
            meal_type = planned_meal.get("meal_type", "")
            query = planned_meal.get("query", "restaurant")

            # Find matching meal_slot with coordinates
            matching_slot = None
            for slot in meal_slots:
                if slot["day"] == day and slot["meal_type"] == meal_type:
                    matching_slot = slot
                    break

            if not matching_slot or (matching_slot["lat"] == 0 and matching_slot["lng"] == 0):
                logger.warning(f"   No coords for Day {day} {meal_type}, skipping search")
                continue

            search_tasks.append(
                search_restaurants_for_meal.ainvoke({
                    "query": query,
                    "lat": matching_slot["lat"],
                    "lng": matching_slot["lng"],
                    "page_size": 3,
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
            if not m["search_results"]:
                continue
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
                meal_date = trip_start + timedelta(days=m["day"])
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
                "user_cuisine_preferences": restaurant_ctx.get("user_cuisine_preferences", []),
                "user_dietary_restrictions": restaurant_ctx.get("user_dietary_restrictions", []),
                "notes": restaurant_ctx.get("notes", ""),
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

            restaurant_result = {"meals": selected_meals}

        logger.info(f"   Phase 3: Selected {len(restaurant_result.get('meals', []))} restaurants")

    except Exception as e:
        logger.error(f"   ❌ Restaurant Agent error: {e}", exc_info=True)
        restaurant_result = {"error": str(e), "meals": []}

    num_meals = len(restaurant_result.get("meals", []))
    logger.info(f"🍽️ [RESTAURANT_AGENT] Completed: {num_meals} meals matched")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"restaurant_agent": restaurant_result},
        "messages": [AIMessage(content=f"[Restaurant Agent] Found restaurants for {num_meals} meals")],
    }
