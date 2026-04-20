"""
Select & Apply Node — Processes flight/hotel selection from search results.

When a user selects a hotel or flight from previous standalone search results,
this node:
1. Uses LLM to match user's selection to the actual options list
2. Resolves placeId if needed
3. Updates current_plan with the selected option
4. If an existing itinerary exists:
   - Builds constraint_overrides (same mechanism as user-provided times)
   - Updates _cached_pipeline (schedule_constraints, distance_pairs)
   - Generates an auto_user_message for Itinerary Modify mode
   - Sets selection_update flag so Itinerary knows this is a selection-triggered rerange
"""

import asyncio
import copy
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _get_latest_user_message
from src.services.itinerary_builder_nonVRP import (
    _resolve_single_place,
    build_location_list,
    build_symmetric_distance_pairs,
    _parse_hotel_time,
)
from src.tools.itinerary_tools import _build_distance_matrix
from src.tools.maps_tools import LOCAL_TRANSPORT_MAP
from src.config import settings

logger = logging.getLogger(__name__)


# ── LLM for selection matching ───────────────────────────────────────────

llm_select = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0,
    streaming=False,
)

SELECT_MATCH_SYSTEM = """\
You are a selection matcher for a travel planning system.

Given a list of available options and the user's message, determine which option the user selected.

RULES:
- Match by name, number, ordinal ("first", "thứ 2"), or partial name
- If the user clearly refers to one option, return its index (0-based)
- If unclear, invalid, or no match, return selected_index: -1 AND provide a `clarification_response` asking the user to clarify their choice. This response MUST be in the SAME language the user used in their message.
- Response MUST be JSON only

Response format:
{
    "selected_index": 0,
    "confidence": "high",
    "target_day": 1, 
    "target_meal_type": "lunch",
    "clarification_response": "I'm not sure which one you mean, could you clarify?" 
}
Note: Day and meal_type are ONLY extracted if the user explicitly specifies them. If not, omit them. clarification_response is ONLY needed if selected_index is -1.
"""


# ── LLM-based selection matching ─────────────────────────────────────────

async def _llm_match_hotel(hotel_search: dict, user_message: str) -> dict | None:
    """Use LLM to match user's selection to hotel search results."""
    segments = hotel_search.get("segments", [])
    if not segments:
        return None

    # Build options list for LLM
    options = []
    option_refs = []  # parallel list to map index → actual data

    for seg in segments:
        rec_name = seg.get("recommend_hotel_name", "")
        rate = seg.get("totalRate", "")
        rating = seg.get("overallRating", "")
        options.append(f"{rec_name} (rate: {rate}, rating: {rating})")
        option_refs.append({
            "name": rec_name,
            "segment": seg,
            "is_recommended": True,
        })

        for alt in seg.get("alternatives", []):
            alt_name = alt.get("name", "")
            alt_rate = alt.get("totalRate", "")
            alt_rating = alt.get("overallRating", "")
            options.append(f"{alt_name} (rate: {alt_rate}, rating: {alt_rating})")
            option_refs.append({
                "name": alt_name,
                "alt_data": alt,
                "segment": seg,
                "is_recommended": False,
            })

    options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))

    try:
        result = await llm_select.ainvoke([
            SystemMessage(content=SELECT_MATCH_SYSTEM),
            HumanMessage(content=f"Available hotels:\n{options_text}\n\nUser said: \"{user_message}\""),
        ])
        parsed = _extract_json(result.content)
        idx = parsed.get("selected_index", -1)
        if 0 <= idx < len(option_refs):
            logger.info(f"🛒 [SELECT_APPLY] LLM matched hotel index {idx}: {option_refs[idx]['name']}")
            return option_refs[idx]
        else:
            return {"_is_clarification": True, "clarification_response": parsed.get("clarification_response")}
    except Exception as e:
        logger.error(f"🛒 [SELECT_APPLY] LLM hotel match failed: {e}")

    return None


async def _llm_match_flight(flight_search: dict, user_message: str) -> dict | None:
    """Use LLM to match user's selection to flight search results."""
    options = []
    option_refs = []

    # Recommended flight
    rec_out = flight_search.get("recommend_outbound_flight", {})
    rec_ret = flight_search.get("recommend_return_flight", {})
    if rec_out:
        desc = (
            f"{rec_out.get('airline', '')} {rec_out.get('flight_number', '')} "
            f"({rec_out.get('departure_time', '?')} → {rec_out.get('arrival_time', '?')})"
        )
        if rec_ret:
            desc += (
                f" + Return: {rec_ret.get('airline', '')} {rec_ret.get('flight_number', '')} "
                f"({rec_ret.get('departure_time', '?')} → {rec_ret.get('arrival_time', '?')})"
            )
        price = flight_search.get("totalPrice", "")
        options.append(f"{desc} — {price}")
        option_refs.append({
            "outbound": rec_out,
            "return": rec_ret,
            "totalPrice": flight_search.get("totalPrice"),
            "is_recommended": True,
        })

    # Alternatives
    for alt in flight_search.get("alternatives", []):
        alt_out = alt.get("outbound_flight") or alt
        alt_ret = alt.get("return_flight") or {}
        desc = (
            f"{alt_out.get('airline', '')} {alt_out.get('flight_number', '')} "
            f"({alt_out.get('departure_time', '?')} → {alt_out.get('arrival_time', '?')})"
        )
        if alt_ret:
            desc += (
                f" + Return: {alt_ret.get('airline', '')} {alt_ret.get('flight_number', '')} "
                f"({alt_ret.get('departure_time', '?')} → {alt_ret.get('arrival_time', '?')})"
            )
        price = alt.get("totalPrice") or alt.get("price", "")
        options.append(f"{desc} — {price}")
        option_refs.append({
            "outbound": alt_out,
            "return": alt_ret,
            "totalPrice": price,
            "is_recommended": False,
            "alt_data": alt,
        })

    if not options:
        return None

    options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))

    try:
        result = await llm_select.ainvoke([
            SystemMessage(content=SELECT_MATCH_SYSTEM),
            HumanMessage(content=f"Available flights:\n{options_text}\n\nUser said: \"{user_message}\""),
        ])
        parsed = _extract_json(result.content)
        idx = parsed.get("selected_index", -1)
        if 0 <= idx < len(option_refs):
            logger.info(f"🛒 [SELECT_APPLY] LLM matched flight index {idx}")
            return option_refs[idx]
        else:
            return {"_is_clarification": True, "clarification_response": parsed.get("clarification_response")}
    except Exception as e:
        logger.error(f"🛒 [SELECT_APPLY] LLM flight match failed: {e}")

    return None


# ── Main Node ────────────────────────────────────────────────────────────

async def select_and_apply_node(state: GraphState) -> dict[str, Any]:
    """Select & Apply Node — Processes flight/hotel selection from search results.

    Uses LLM to match user's selection to cached search results,
    resolves placeId, updates current_plan, and optionally triggers
    itinerary rerange via constraint_overrides.
    """
    logger.info("=" * 60)
    logger.info("🛒 [SELECT_APPLY] Node entered")

    intent = state.get("routed_intent", "")
    current_plan = state.get("current_plan", {})
    user_message = _get_latest_user_message(state)
    
    plan_context = current_plan.get("plan_context", {})
    language = plan_context.get("language", "en")

    if not user_message:
        logger.warning("🛒 [SELECT_APPLY] No user message found")
        msg = "Tôi không hiểu bạn muốn chọn gì. Vui lòng nói rõ tên lựa chọn của bạn." if language == "vi" else "I don't understand what you want to select. Please specify your choice."
        return {
            "current_plan": current_plan,
            "final_response": msg,
            "messages": [AIMessage(content="[Select Apply] No user message")],
        }

    logger.info(f"🛒 [SELECT_APPLY] Intent: {intent}, User: '{user_message[:80]}'")

    if intent == "select_hotel":
        return await _handle_hotel_selection(state, current_plan, user_message)
    elif intent == "select_flight":
        return await _handle_flight_selection(state, current_plan, user_message)
    elif intent == "select_restaurant":
        return await _handle_restaurant_selection(state, current_plan, user_message)
    else:
        logger.warning(f"🛒 [SELECT_APPLY] Unknown intent: {intent}")
        msg = "Yêu cầu lựa chọn không hợp lệ." if language == "vi" else "Invalid selection request."
        return {
            "current_plan": current_plan,
            "final_response": msg,
            "messages": [AIMessage(content=f"[Select Apply] Unknown intent: {intent}")],
        }


async def _handle_hotel_selection(
    state: GraphState, current_plan: dict, user_message: str
) -> dict[str, Any]:
    """Handle hotel selection: LLM match → resolve → update plan → build overrides."""
    logger.info("🏨 [SELECT_APPLY] Processing hotel selection...")

    existing_itinerary = current_plan.get("itinerary", {})
    has_itinerary = bool(existing_itinerary.get("days"))
    plan_context = current_plan.get("plan_context", {})
    language = plan_context.get("language", "en")

    if not has_itinerary:
        logger.info("🏨 [SELECT_APPLY] No itinerary — blocking selection")
        msg = "Bạn chưa có lịch trình nào. Hãy yêu cầu tôi tạo lịch trình trước khi chọn khách sạn nhé." if language == "vi" else "You don't have an itinerary yet. Please ask me to create an itinerary before selecting a hotel."
        return {
            "current_plan": current_plan,
            "routed_intent": "select_hotel",
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    hotel_search = current_plan.get("hotel_search", {})
    if not hotel_search or not hotel_search.get("segments"):
        logger.warning("🏨 [SELECT_APPLY] No hotel_search results in current_plan")
        msg = "Chưa có kết quả tìm kiếm khách sạn. Hãy tìm kiếm trước." if language == "vi" else "No hotel search results available. Please search first."
        return {
            "current_plan": current_plan,
            "final_response": msg,
            "messages": [AIMessage(content="[Select Apply] No hotel search results")],
        }

    # 1. LLM match user's selection
    match = await _llm_match_hotel(hotel_search, user_message)
    if not match or match.get("_is_clarification"):
        logger.warning(f"🏨 [SELECT_APPLY] LLM could not match selection")
        fallback_msg = match.get("clarification_response") if match else None
        if not fallback_msg:
            fallback_msg = "Tôi không rõ bạn muốn chọn khách sạn nào. Vui lòng nói rõ tên khách sạn." if language == "vi" else "I'm not sure which hotel you want to select. Please specify the name."
        return {
            "current_plan": current_plan,
            "final_response": fallback_msg,
            "messages": [AIMessage(content=f"[Select Apply] Hotel match failed: {fallback_msg}")],
        }

    hotel_name = match["name"]
    segment = match["segment"]
    logger.info(f"🏨 [SELECT_APPLY] Matched hotel: '{hotel_name}' (recommended={match['is_recommended']})")

    # 2. Get hotel details
    if match["is_recommended"]:
        hotel_placeId = segment.get("recommend_hotel_placeId", "")
        hotel_location = segment.get("_location")
        check_in_time = _parse_hotel_time(segment.get("check_in_time", "14:00"))
        check_out_time = _parse_hotel_time(segment.get("check_out_time", "12:00"))
        total_rate = segment.get("totalRate", "")
        check_in_date = segment.get("check_in", "")
        check_out_date = segment.get("check_out", "")
    else:
        alt_data = match.get("alt_data", {})
        # Use pre-resolved data from Hotel Agent if available
        hotel_placeId = alt_data.get("placeId", "")
        hotel_location = alt_data.get("_location")
        # Use alternative-specific check-in/out times if available, fallback to segment
        check_in_time = _parse_hotel_time(
            alt_data.get("checkInTime") or segment.get("check_in_time", "14:00")
        )
        check_out_time = _parse_hotel_time(
            alt_data.get("checkOutTime") or segment.get("check_out_time", "12:00")
        )
        total_rate = alt_data.get("totalRate", "")
        check_in_date = segment.get("check_in", "")
        check_out_date = segment.get("check_out", "")

    # 3. Resolve placeId if needed
    if not hotel_placeId:
        logger.info(f"🏨 [SELECT_APPLY] Resolving placeId for '{hotel_name}'...")
        try:
            resolved = await _resolve_single_place(hotel_name)
            if resolved:
                hotel_placeId = resolved.get("placeId", "")
                hotel_location = resolved.get("location")
                logger.info(f"🏨 [SELECT_APPLY] Resolved: '{hotel_name}' → {hotel_placeId}")
        except Exception as e:
            logger.error(f"🏨 [SELECT_APPLY] Resolve failed for '{hotel_name}': {e}")

    # 4. Update current_plan
    plan_context = current_plan.get("plan_context", {})
    current_plan["selected_hotel"] = {
        "name": hotel_name,
        "placeId": hotel_placeId,
        "location": hotel_location,
        "check_in_time": check_in_time,
        "check_out_time": check_out_time,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "totalRate": total_rate,
    }
    logger.info(f"🏨 [SELECT_APPLY] Updated current_plan.selected_hotel: {hotel_name}")

    # 5. Check if itinerary exists → prepare rerange
    existing_itinerary = current_plan.get("itinerary", {})
    has_itinerary = bool(existing_itinerary.get("days"))

    if has_itinerary:
        logger.info("🏨 [SELECT_APPLY] Existing itinerary found — preparing rerange...")

        # Build constraint_overrides for hotel
        num_days = plan_context.get("num_days", 1)
        constraint_overrides = {
            "hotels": [{
                "nights": list(range(1, num_days)),
                "check_in_time": check_in_time,
                "check_out_time": check_out_time,
            }]
        }

        # Update _cached_pipeline with new hotel info
        cached_pipeline = copy.deepcopy(existing_itinerary.get("_cached_pipeline", {}))
        schedule_constraints = cached_pipeline.get("schedule_constraints", {})

        for h in schedule_constraints.get("hotels", []):
            h["name"] = hotel_name
            h["check_in_time"] = check_in_time
            h["check_out_time"] = check_out_time

        # Update hotel name in existing schedule stops
        existing_days = existing_itinerary.get("days", [])
        old_hotel_names = set()
        for h in existing_itinerary.get("_cached_pipeline", {}).get("schedule_constraints", {}).get("hotels", []):
            old_hotel_names.add(h.get("name", "").lower())

        for day in existing_days:
            for stop in day.get("stops", []):
                roles = stop.get("role", [])
                if isinstance(roles, str):
                    roles = [roles]
                hotel_roles = {"check_in", "check_out", "end_day", "start_day", "rest", "luggage_drop", "luggage_pickup"}
                if set(roles) & hotel_roles:
                    stop_name = stop.get("name", "").lower()
                    if stop_name in old_hotel_names or not stop_name:
                        stop["name"] = hotel_name

        # Recompute distance matrix if new hotel has location
        if hotel_location and hotel_placeId:
            try:
                logger.info("🏨 [SELECT_APPLY] Recomputing distance matrix with new hotel...")
                resolved_places = copy.deepcopy(existing_itinerary.get("resolved_places", {}))

                for h_info in resolved_places.get("hotels", []):
                    h_info["name"] = hotel_name
                    h_info["resolved"] = {
                        "placeId": hotel_placeId,
                        "title": hotel_name,
                        "location": hotel_location,
                    }

                locations = build_location_list(resolved_places)
                if len(locations) >= 2:
                    transport = plan_context.get("local_transportation", "car")
                    travel_mode = LOCAL_TRANSPORT_MAP.get(transport, "DRIVE")
                    distance_matrix = await _build_distance_matrix(locations, travel_mode)
                    if distance_matrix:
                        new_distance_pairs = build_symmetric_distance_pairs(locations, distance_matrix)
                        cached_pipeline["distance_pairs"] = new_distance_pairs
                        logger.info(f"🏨 [SELECT_APPLY] Distance matrix updated: {len(new_distance_pairs)} pairs")

                existing_itinerary["resolved_places"] = resolved_places

            except Exception as e:
                logger.error(f"🏨 [SELECT_APPLY] Distance matrix recompute failed: {e}")

        cached_pipeline["schedule_constraints"] = schedule_constraints
        existing_itinerary["_cached_pipeline"] = cached_pipeline
        current_plan["itinerary"] = existing_itinerary

        # Build auto user message for Itinerary Modify
        auto_msg = (
            f"Hotel changed to \"{hotel_name}\". "
            f"Check-in: {check_in_time}, Check-out: {check_out_time}. "
            f"Update hotel name in all related stops (start_day, end_day, check_in, check_out, rest, luggage). "
            f"Verify timing around check-in/check-out. Keep the rest unchanged."
        )

        selection_update = {
            "type": "hotel",
            "hotel_name": hotel_name,
            "hotel_placeId": hotel_placeId,
            "needs_rerange": True,
            "auto_user_message": auto_msg,
            "constraint_overrides": constraint_overrides,
        }

        return {
            "current_plan": current_plan,
            "selection_update": selection_update,
            "constraint_overrides": constraint_overrides,
            "agent_outputs": {
                "hotel_agent": {
                    "segments": [{
                        "recommend_hotel_name": hotel_name,
                        "totalRate": total_rate,
                        "check_in": current_plan.get("plan_context", {}).get("start_date", ""),
                        "check_out": current_plan.get("plan_context", {}).get("end_date", ""),
                        "segment_name": match.get("segment_name", "Selected Hotel")
                    }]
                }
            },
            "routed_intent": "select_hotel",
            "messages": [AIMessage(content=f"[Select Apply] Hotel selected: {hotel_name}, rerange triggered")],
        }

    # We don't need the else block since has_itinerary is now guaranteed above
    logger.error("🏨 [SELECT_APPLY] Reached unreachable code (hotel no itinerary)")
    return {"current_plan": current_plan}


async def _handle_flight_selection(
    state: GraphState, current_plan: dict, user_message: str
) -> dict[str, Any]:
    """Handle flight selection: LLM match → extract times → build overrides."""
    logger.info("✈️ [SELECT_APPLY] Processing flight selection...")

    existing_itinerary = current_plan.get("itinerary", {})
    has_itinerary = bool(existing_itinerary.get("days"))
    plan_context = current_plan.get("plan_context", {})
    language = plan_context.get("language", "en")

    if not has_itinerary:
        logger.info("✈️ [SELECT_APPLY] No itinerary — blocking selection")
        msg = "Bạn chưa có lịch trình nào. Hãy yêu cầu tôi tạo lịch trình trước khi chọn chuyến bay nhé." if language == "vi" else "You don't have an itinerary yet. Please ask me to create an itinerary before selecting a flight."
        return {
            "current_plan": current_plan,
            "routed_intent": "select_flight",
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    flight_search = current_plan.get("flight_search", {})
    if not flight_search:
        logger.warning("✈️ [SELECT_APPLY] No flight_search results in current_plan")
        msg = "Chưa có kết quả tìm kiếm chuyến bay. Hãy tìm kiếm trước." if language == "vi" else "No flight search results available. Please search first."
        return {
            "current_plan": current_plan,
            "final_response": msg,
            "messages": [AIMessage(content="[Select Apply] No flight search results")],
        }

    # 1. LLM match user's selection
    match = await _llm_match_flight(flight_search, user_message)
    if not match or match.get("_is_clarification"):
        logger.warning("✈️ [SELECT_APPLY] LLM could not match flight selection")
        fallback_msg = match.get("clarification_response") if match else None
        if not fallback_msg:
            fallback_msg = "Tôi không rõ bạn muốn chọn chuyến bay nào. Vui lòng cung cấp chi tiết hãng hoặc giờ bay." if language == "vi" else "I'm not sure which flight you want to select. Please specify details like airline or time."
        return {
            "current_plan": current_plan,
            "final_response": fallback_msg,
            "messages": [AIMessage(content=f"[Select Apply] Flight match failed: {fallback_msg}")],
        }

    outbound = match.get("outbound") or {}
    return_flight = match.get("return") or {}
    total_price = match.get("totalPrice", 0)
    logger.info(
        f"✈️ [SELECT_APPLY] Matched flight: "
        f"outbound={outbound.get('flight_number', '?')}, "
        f"return={return_flight.get('flight_number', '?')}"
    )

    # 2. Store selected flight
    current_plan["selected_flight"] = {
        "outbound": outbound,
        "return": return_flight,
        "totalPrice": total_price,
    }

    flight_agent_data = {
        "recommend_outbound_flight": outbound,
        "recommend_return_flight": return_flight,
        "totalPrice": total_price,
        "type": flight_search.get("type", "one_way"),
    }

    # 3. Build constraint_overrides
    constraint_overrides = {}
    if outbound:
        if outbound.get("departure_time"):
            constraint_overrides["outbound_departure_time"] = outbound["departure_time"]
        if outbound.get("arrival_time"):
            constraint_overrides["outbound_arrival_time"] = outbound["arrival_time"]
    if return_flight:
        if return_flight.get("departure_time"):
            constraint_overrides["return_departure_time"] = return_flight["departure_time"]
        if return_flight.get("arrival_time"):
            constraint_overrides["return_arrival_time"] = return_flight["arrival_time"]

    logger.info(f"✈️ [SELECT_APPLY] Constraint overrides: {constraint_overrides}")

    # 4. Check itinerary for rerange
    existing_itinerary = current_plan.get("itinerary", {})
    has_itinerary = bool(existing_itinerary.get("days"))
    plan_context = current_plan.get("plan_context", {})

    if has_itinerary:
        logger.info("✈️ [SELECT_APPLY] Existing itinerary found — preparing rerange...")

        existing_days = existing_itinerary.get("days", [])
        for day in existing_days:
            for stop in day.get("stops", []):
                roles = stop.get("role", [])
                if isinstance(roles, str):
                    roles = [roles]
                if "outbound_arrival" in roles and outbound:
                    stop["name"] = outbound.get("arrival_airport_name", stop.get("name", ""))
                elif "return_departure" in roles and return_flight:
                    stop["name"] = return_flight.get("departure_airport_name", stop.get("name", ""))

        current_plan["itinerary"] = existing_itinerary

        # Build auto user message
        language = plan_context.get("language", "en")
        outbound_info = ""
        return_info = ""
        if outbound:
            outbound_info = (
                f"Outbound: {outbound.get('airline', '')} {outbound.get('flight_number', '')}, "
                f"depart {outbound.get('departure_time', '?')} → arrive {outbound.get('arrival_time', '?')}"
            )
        if return_flight:
            return_info = (
                f"Return: {return_flight.get('airline', '')} {return_flight.get('flight_number', '')}, "
                f"depart {return_flight.get('departure_time', '?')} → arrive {return_flight.get('arrival_time', '?')}"
            )

        if language == "vi":
            auto_msg = (
                f"Chuyến bay đã đổi. {outbound_info}. {return_info}. "
                f"Cập nhật ngày đầu (outbound_arrival) và ngày cuối (return_departure). "
                f"Nếu đến sớm hơn → có thể thêm hoạt động. Đến muộn hơn → bỏ bớt hoặc dời. "
                f"Tương tự cho ngày về. Giữ nguyên các ngày giữa."
            )
        else:
            auto_msg = (
                f"Flight changed. {outbound_info}. {return_info}. "
                f"Update day 1 (outbound_arrival) and last day (return_departure). "
                f"If arriving earlier → add activities. Arriving later → remove or shift. "
                f"Same for return day. Keep middle days unchanged."
            )

        selection_update = {
            "type": "flight",
            "needs_rerange": True,
            "auto_user_message": auto_msg,
            "constraint_overrides": constraint_overrides,
            "flight_agent_data": flight_agent_data,
        }

        return {
            "current_plan": current_plan,
            "selection_update": selection_update,
            "constraint_overrides": constraint_overrides,
            "agent_outputs": {"flight_agent": flight_agent_data},
            "routed_intent": "select_flight",
            "messages": [AIMessage(content="[Select Apply] Flight selected, rerange triggered")],
        }

    # We don't need the else block since has_itinerary is now guaranteed above
    logger.error("✈️ [SELECT_APPLY] Reached unreachable code (flight no itinerary)")
    return {"current_plan": current_plan}


async def _llm_match_restaurant(restaurant_search: dict, user_message: str) -> dict | None:
    """Use LLM to match user's selection to restaurant search results."""
    meals = restaurant_search.get("meals", [])
    if not meals:
        return None

    options = []
    option_refs = []

    for m in meals:
        # Original result
        if "name" in m:
            desc = f"{m['name']} (Day {m.get('day', '?')} {m.get('meal_type', '?')}) - Rating: {m.get('rating', 'N/A')}"
            options.append(desc)
            option_refs.append({
                "name": m["name"],
                "meal": m,
                "is_alternative": False,
            })
            
        # Alternatives
        for alt in m.get("alternatives", []):
            if "name" in alt:
                desc = f"{alt['name']} (Alternative for Day {m.get('day', '?')} {m.get('meal_type', '?')}) - Rating: {alt.get('rating', 'N/A')}"
                options.append(desc)
                option_refs.append({
                    "name": alt["name"],
                    "meal": m,
                    "alt_data": alt,
                    "is_alternative": True,
                })

    if not options:
        return None

    options_text = "\n".join(f"{i+1}. {opt}" for i, opt in enumerate(options))

    try:
        result = await llm_select.ainvoke([
            SystemMessage(content=SELECT_MATCH_SYSTEM),
            HumanMessage(content=f"Available restaurants:\n{options_text}\n\nUser said: \"{user_message}\""),
        ])
        parsed = _extract_json(result.content)
        idx = parsed.get("selected_index", -1)
        if 0 <= idx < len(option_refs):
            logger.info(f"🛒 [SELECT_APPLY] LLM matched restaurant index {idx}: {option_refs[idx]['name']}")
            match_data = option_refs[idx]
            match_data["target_day"] = parsed.get("target_day")
            match_data["target_meal_type"] = parsed.get("target_meal_type")
            return match_data
        else:
            return {"_is_clarification": True, "clarification_response": parsed.get("clarification_response")}
    except Exception as e:
        logger.error(f"🛒 [SELECT_APPLY] LLM restaurant match failed: {e}")

    return None

async def _handle_restaurant_selection(
    state: GraphState, current_plan: dict, user_message: str
) -> dict[str, Any]:
    """Handle restaurant selection."""
    logger.info("🍽️ [SELECT_APPLY] Processing restaurant selection...")

    existing_itinerary = current_plan.get("itinerary", {})
    has_itinerary = bool(existing_itinerary.get("days"))
    plan_context = current_plan.get("plan_context", {})
    language = plan_context.get("language", "en")

    if not has_itinerary:
        logger.info("🍽️ [SELECT_APPLY] No itinerary — blocking selection")
        msg = "Bạn chưa có lịch trình nào. Hãy yêu cầu tôi tạo lịch trình trước khi chọn nhà hàng nhé." if language == "vi" else "You don't have an itinerary yet. Please ask me to create an itinerary before selecting a restaurant."
        return {
            "current_plan": current_plan,
            "routed_intent": "select_restaurant",
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    restaurant_search = current_plan.get("restaurant_search", {})
    if not restaurant_search or not restaurant_search.get("meals"):
        msg = "Chưa có kết quả tìm kiếm quán ăn." if language == "vi" else "No restaurant search results available."
        return {
            "current_plan": current_plan,
            "final_response": msg,
            "messages": [AIMessage(content="[Select Apply] No restaurant search results")],
        }

    # 1. Match selection
    match = await _llm_match_restaurant(restaurant_search, user_message)
    if not match or match.get("_is_clarification"):
        fallback_msg = match.get("clarification_response") if match else None
        if not fallback_msg:
            fallback_msg = "Tôi không rõ bạn muốn chọn quán ăn nào. Vui lòng nói rõ tên." if language == "vi" else "I'm not sure which restaurant you want to select. Please specify the name."
        return {
            "current_plan": current_plan,
            "final_response": fallback_msg,
            "messages": [AIMessage(content=f"[Select Apply] Failed to match restaurant: {fallback_msg}")],
        }

    selected_place = match.get("alt_data") if match.get("is_alternative") else match.get("meal")
    place_name = selected_place.get("name", "")
    place_id = selected_place.get("place_id", "")
    
    # 2. Extract intended target
    orig_meal = match.get("meal", {})
    target_day = match.get("target_day") or orig_meal.get("day")
    target_meal_type = match.get("target_meal_type") or orig_meal.get("meal_type")
    
    logger.info(f"🍽️ [SELECT_APPLY] Selected '{place_name}' for Day {target_day} {target_meal_type}")

    # 3. Direct modification of itinerary if it exists
    itinerary = current_plan.get("itinerary", {})
    applied = False
    
    if itinerary and "days" in itinerary and target_day and target_meal_type:
        for day in itinerary["days"]:
            if day.get("day") == target_day:
                for stop in day.get("stops", []):
                    roles = stop.get("role", stop.get("roles", []))
                    if isinstance(roles, str):
                        roles = [roles]
                    if target_meal_type in roles:
                        stop["name"] = place_name
                        stop["placeId"] = place_id
                        applied = True
                        break
        
        if applied:
            # We must set rerange=False so it flows to synthesize
            # synthesize will output the modified itinerary!
            logger.info("🍽️ [SELECT_APPLY] Directly modified itinerary for restaurant!")
            return {
                "current_plan": current_plan,
                "selection_update": {"type": "restaurant", "needs_rerange": False},
                "routed_intent": "select_restaurant",
                "agent_outputs": {"itinerary_agent": itinerary},
                "messages": [AIMessage(content=f"[Select Apply] Applied restaurant {place_name}")],
            }

    # If could not apply to itinerary (e.g. standalone search without itinerary, or slot not found)
    msg = "Đã xảy ra lỗi hệ thống: Không thể áp dụng quán ăn này vào lịch trình của bạn. Vui lòng thử lại." if language == "vi" else "System error: Could not apply this restaurant to your itinerary. Please try again."
    return {
        "current_plan": current_plan,
        "selection_update": {"type": "restaurant", "needs_rerange": False},
        "routed_intent": "select_restaurant",
        "final_response": msg,
        "messages": [AIMessage(content=msg)],
    }
