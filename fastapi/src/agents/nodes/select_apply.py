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
   - Sets constraint_overrides flag so Itinerary knows this is a selection-triggered rerange
"""

import asyncio
import copy
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.services.itinerary_builder import (
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

HOTEL_SELECT_MATCH_SYSTEM = """\
You are a hotel selection matcher for a travel planning system.

Given a list of available hotels grouped by segment (location/dates) and the user's message, determine which hotel the user selected for each segment.
Return a list of selections, where each selection specifies the `segment_index` and the 0-based `selected_hotel_index` within that segment.
If the user's message is ambiguous, or they ask to select a hotel not in the list, return an empty array for `selections` and provide a `clarification_response` asking them to clarify in the SAME language the user used.
You only need to return selections for segments where the user explicitly chose a hotel.

Response format:
{
    "selections": [
        { "segment_index": 0, "selected_hotel_index": 1 }
    ],
    "clarification_response": "..."
}
"""

async def _llm_match_hotel(hotel_search: dict, user_message: str) -> list[dict] | dict | None:
    """Use LLM to match user's selection to hotel search results. Returns a list of matched options or a clarification dict."""
    segments = hotel_search.get("segments", [])
    if not segments:
        return None

    # Build options list for LLM grouped by segment
    options_text_parts = []
    option_refs = {}  # map (segment_idx, hotel_idx) → actual data

    for seg_idx, seg in enumerate(segments):
        seg_name = seg.get("segment_name", f"Segment {seg_idx}")
        options_text_parts.append(f"Segment {seg_idx}: {seg_name}")
        
        hotel_idx = 0
        rec_name = seg.get("recommend_hotel_name", "")
        rate = seg.get("totalRate", "")
        rating = seg.get("overallRating", "")
        
        options_text_parts.append(f"  {hotel_idx}. RECOMMENDED: {rec_name} (rate: {rate}, rating: {rating})")
        option_refs[(seg_idx, hotel_idx)] = {
            "name": rec_name,
            "segment": seg,
            "segment_idx": seg_idx,
            "is_recommended": True,
        }
        hotel_idx += 1

        for alt in seg.get("alternatives", []):
            alt_name = alt.get("name", "")
            alt_rate = alt.get("totalRate", "")
            alt_rating = alt.get("overallRating", "")
            options_text_parts.append(f"  {hotel_idx}. ALTERNATIVE: {alt_name} (rate: {alt_rate}, rating: {alt_rating})")
            option_refs[(seg_idx, hotel_idx)] = {
                "name": alt_name,
                "alt_data": alt,
                "segment": seg,
                "segment_idx": seg_idx,
                "is_recommended": False,
            }
            hotel_idx += 1
            
        options_text_parts.append("")

    options_text = "\n".join(options_text_parts)

    try:
        result = await llm_select.ainvoke([
            SystemMessage(content=HOTEL_SELECT_MATCH_SYSTEM),
            HumanMessage(content=f"Available hotels:\n{options_text}\n\nUser said: \"{user_message}\""),
        ])
        parsed = _extract_json(result.content)
        selections = parsed.get("selections", [])
        
        matches = []
        for sel in selections:
            s_idx = sel.get("segment_index", -1)
            h_idx = sel.get("selected_hotel_index", -1)
            ref = option_refs.get((s_idx, h_idx))
            if ref:
                matches.append(ref)
                
        if matches:
            logger.info(f"🛒 [SELECT_APPLY] LLM matched hotels: {[m['name'] for m in matches]}")
            return matches
        else:
            return {"_is_clarification": True, "clarification_response": parsed.get("clarification_response")}
    except Exception as e:
        logger.error(f"🛒 [SELECT_APPLY] LLM hotel match failed: {e}")

    return None


FLIGHT_SELECT_MATCH_SYSTEM = """\
You are a flight selection matcher for a travel planning system.

Given lists of available outbound and return flights, and the user's message, determine which flights the user selected.

RULES:
- Match by flight number (e.g. VU 751, VN 123), airline name, time, or ordinal ("first outbound", "second return").
- If the user clearly refers to an outbound flight, return its 0-based index in `selected_outbound_index`. Otherwise, return -1.
- If the user clearly refers to a return flight, return its 0-based index in `selected_return_index`. Otherwise, return -1.
- If the user's message is ambiguous or none of the flights match what they asked for, return -1 for both and provide a `clarification_response` asking for clarification in the SAME language the user used.
- Response MUST be JSON only.

Response format:
{
    "selected_outbound_index": 0,
    "selected_return_index": -1,
    "clarification_response": "..."
}
"""

async def _llm_match_flight(flight_search: dict, user_message: str) -> dict | None:
    """Use LLM to match user's selection to flight search results."""
    
    outbound_options = []
    outbound_refs = []
    return_options = []
    return_refs = []

    rec_out = flight_search.get("recommend_outbound_flight", {})
    if rec_out:
        desc = f"RECOMMENDED: {rec_out.get('airline', '')} {rec_out.get('flight_number', '')} ({rec_out.get('departure_time', '?')} → {rec_out.get('arrival_time', '?')}) — {rec_out.get('price', '')}"
        outbound_options.append(desc)
        outbound_refs.append(rec_out)
        
    rec_ret = flight_search.get("recommend_return_flight", {})
    if rec_ret:
        desc = f"RECOMMENDED: {rec_ret.get('airline', '')} {rec_ret.get('flight_number', '')} ({rec_ret.get('departure_time', '?')} → {rec_ret.get('arrival_time', '?')}) — {rec_ret.get('price', '')}"
        return_options.append(desc)
        return_refs.append(rec_ret)

    # Alternatives
    for alt in flight_search.get("alternatives", []):
        direction = alt.get("direction", "")
        # Handle legacy nested format
        if "outbound_flight" in alt:
            alt_out = alt["outbound_flight"]
            desc_out = f"ALTERNATIVE: {alt_out.get('airline', '')} {alt_out.get('flight_number', '')} ({alt_out.get('departure_time', '?')} → {alt_out.get('arrival_time', '?')}) — {alt_out.get('price', '')}"
            outbound_options.append(desc_out)
            outbound_refs.append(alt_out)
            
            if "return_flight" in alt:
                alt_ret = alt["return_flight"]
                desc_ret = f"ALTERNATIVE: {alt_ret.get('airline', '')} {alt_ret.get('flight_number', '')} ({alt_ret.get('departure_time', '?')} → {alt_ret.get('arrival_time', '?')}) — {alt_ret.get('price', '')}"
                return_options.append(desc_ret)
                return_refs.append(alt_ret)
        else:
            desc = f"ALTERNATIVE: {alt.get('airline', '')} {alt.get('flight_number', '')} ({alt.get('departure_time', '?')} → {alt.get('arrival_time', '?')}) — {alt.get('price', '')}"
            if direction == "return":
                return_options.append(desc)
                return_refs.append(alt)
            else:
                outbound_options.append(desc)
                outbound_refs.append(alt)

    if not outbound_options and not return_options:
        return None

    outbound_text = "\n".join(f"{i}. {opt}" for i, opt in enumerate(outbound_options))
    return_text = "\n".join(f"{i}. {opt}" for i, opt in enumerate(return_options))

    prompt = f"Available Outbound Flights:\n{outbound_text}\n\n"
    if return_options:
        prompt += f"Available Return Flights:\n{return_text}\n\n"
    prompt += f"User said: \"{user_message}\""

    try:
        result = await llm_select.ainvoke([
            SystemMessage(content=FLIGHT_SELECT_MATCH_SYSTEM),
            HumanMessage(content=prompt),
        ])
        parsed = _extract_json(result.content)
        
        idx_out = parsed.get("selected_outbound_index", -1)
        idx_ret = parsed.get("selected_return_index", -1)
        
        if idx_out >= 0 or idx_ret >= 0:
            final_outbound = None
            final_return = None
            
            if 0 <= idx_out < len(outbound_refs):
                final_outbound = outbound_refs[idx_out]
                logger.info(f"🛒 [SELECT_APPLY] LLM matched outbound flight index {idx_out}")

            if 0 <= idx_ret < len(return_refs):
                final_return = return_refs[idx_ret]
                logger.info(f"🛒 [SELECT_APPLY] LLM matched return flight index {idx_ret}")
                
            # Calculate price
            total_price = 0
            if flight_search.get("type") == "round_trip":
                total_price = flight_search.get("totalPrice", 0)
            else:
                def parse_price(p):
                    if isinstance(p, (int, float)): return p
                    if isinstance(p, str):
                        try: return int(''.join(c for c in p if c.isdigit()))
                        except: return 0
                    return 0
                
                p_out = parse_price(final_outbound.get("price", 0)) if final_outbound else 0
                p_ret = parse_price(final_return.get("price", 0)) if final_return else 0
                total_price = p_out + p_ret
                if total_price == 0:
                    total_price = flight_search.get("totalPrice", 0)
                    
            return {
                "outbound": final_outbound,
                "return": final_return,
                "totalPrice": total_price
            }
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

    intent = (state.get("intent_output") or {}).get("intent", "")
    current_plan = state.get("current_plan", {})
    user_message = state.get("user_message", "")
    
    plan_context = current_plan.get("plan_context", {})
    language = plan_context.get("language", "en")

    if not user_message:
        logger.warning("🛒 [SELECT_APPLY] No user message found")
        msg = "Tôi không hiểu bạn muốn chọn gì. Vui lòng nói rõ tên lựa chọn của bạn." if language == "vi" else "I don't understand what you want to select. Please specify your choice."
        return {
            "current_plan": current_plan,
            "final_response": msg,

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
            "intent_output": {"intent": "select_hotel"},
            "final_response": msg,

        }

    hotel_search = current_plan.get("hotel_search", {})
    if not hotel_search or not hotel_search.get("segments"):
        logger.warning("🏨 [SELECT_APPLY] No hotel_search results in current_plan")
        msg = "Chưa có kết quả tìm kiếm khách sạn. Hãy tìm kiếm trước." if language == "vi" else "No hotel search results available. Please search first."
        return {
            "current_plan": current_plan,
            "final_response": msg,

        }

    # 1. LLM match user's selection
    matches = await _llm_match_hotel(hotel_search, user_message)
    if not matches or (isinstance(matches, dict) and matches.get("_is_clarification")):
        logger.warning(f"🏨 [SELECT_APPLY] LLM could not match selection")
        fallback_msg = matches.get("clarification_response") if isinstance(matches, dict) else None
        if not fallback_msg:
            fallback_msg = "Tôi không rõ bạn muốn chọn khách sạn nào. Vui lòng nói rõ tên khách sạn." if language == "vi" else "I'm not sure which hotel you want to select. Please specify the name."
        return {
            "current_plan": current_plan,
            "final_response": fallback_msg,

        }

    # Preparation for itinerary updates
    existing_itinerary = current_plan.get("itinerary", {})
    has_itinerary = bool(existing_itinerary.get("days"))
    plan_context = current_plan.get("plan_context", {})
    
    cached_pipeline = copy.deepcopy(existing_itinerary.get("_cached_pipeline", {})) if has_itinerary else {}
    schedule_constraints = cached_pipeline.get("schedule_constraints", {})
    existing_days = existing_itinerary.get("days", [])
    resolved_places = copy.deepcopy(existing_itinerary.get("resolved_places", {})) if has_itinerary else {}
    
    constraint_overrides = {"hotels": []}
    auto_msgs = []
    need_distance_recompute = False
    
    last_hotel_name = ""
    last_hotel_placeId = ""

    for match in matches:
        hotel_name = match["name"]
        segment = match["segment"]
        segment_idx = match.get("segment_idx", 0)
        old_hotel_name = segment.get("recommend_hotel_name", "")
        logger.info(f"🏨 [SELECT_APPLY] Processing matched hotel: '{hotel_name}' (recommended={match['is_recommended']})")
        
        last_hotel_name = hotel_name

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
            hotel_placeId = alt_data.get("placeId", "")
            hotel_location = alt_data.get("_location")
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
                
        last_hotel_placeId = hotel_placeId

        # 4. Update current_plan hotel_search segments
        if "segments" in current_plan.get("hotel_search", {}):
            seg_to_update = current_plan["hotel_search"]["segments"][segment_idx]
            seg_to_update["recommend_hotel_name"] = hotel_name
            seg_to_update["recommend_hotel_placeId"] = hotel_placeId
            seg_to_update["totalRate"] = total_rate
            seg_to_update["check_in_time"] = check_in_time
            seg_to_update["check_out_time"] = check_out_time
            if not match["is_recommended"]:
                alt_data = match.get("alt_data", {})
                seg_to_update["link"] = alt_data.get("link", seg_to_update.get("link", ""))
                seg_to_update["thumbnail"] = alt_data.get("thumbnail", seg_to_update.get("thumbnail", ""))
                seg_to_update["overallRating"] = alt_data.get("overallRating", seg_to_update.get("overallRating", ""))
                seg_to_update["reviews"] = alt_data.get("reviews", seg_to_update.get("reviews", 0))
                seg_to_update["hotel_class"] = alt_data.get("hotel_class", seg_to_update.get("hotel_class", ""))

        current_plan["selected_hotel"] = {
            "name": hotel_name,
            "placeId": hotel_placeId,
            "location": hotel_location,
            "check_in_time": check_in_time,
            "check_out_time": check_out_time,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "totalRate": total_rate,
            "segment_idx": segment_idx,
        }

        if has_itinerary:
            target_nights = []
            for h in schedule_constraints.get("hotels", []):
                if h.get("segment_name") == segment.get("segment_name") or h.get("name") == old_hotel_name:
                    h["name"] = hotel_name
                    h["check_in_time"] = check_in_time
                    h["check_out_time"] = check_out_time
                    if h.get("check_in_day"):
                        target_nights.append(h["check_in_day"])

            constraint_overrides["hotels"].append({
                "nights": target_nights,
                "check_in_time": check_in_time,
                "check_out_time": check_out_time,
            })

            # Pre-modify hotel names in existing stops
            for day in existing_days:
                for stop in day.get("stops", []):
                    roles = stop.get("role", [])
                    if isinstance(roles, str):
                        roles = [roles]
                    hotel_roles = {"check_in", "check_out", "end_day", "start_day", "rest", "luggage_drop", "luggage_pickup"}
                    if set(roles) & hotel_roles:
                        stop_name = stop.get("name", "").lower()
                        if stop_name == old_hotel_name.lower() or not stop_name:
                            stop["name"] = hotel_name

            # Update resolved_places for this hotel
            if hotel_location and hotel_placeId:
                for h_info in resolved_places.get("hotels", []):
                    if h_info.get("segment_name") == segment.get("segment_name") or h_info.get("name") == old_hotel_name:
                        h_info["name"] = hotel_name
                        h_info["resolved"] = {
                            "placeId": hotel_placeId,
                            "title": hotel_name,
                            "location": hotel_location,
                        }
                need_distance_recompute = True

            auto_msgs.append(f"Segment '{segment.get('segment_name', '')}': changed to {hotel_name} (check-in {check_in_time}, check-out {check_out_time}).")

    if has_itinerary:
        logger.info("🏨 [SELECT_APPLY] Existing itinerary found — preparing rerange...")

        if need_distance_recompute:
            try:
                logger.info("🏨 [SELECT_APPLY] Recomputing distance matrix with new hotels...")
                from src.services.itinerary_builder import build_location_list, build_symmetric_distance_pairs
                locations = build_location_list(resolved_places)
                if len(locations) >= 2:
                    transport = plan_context.get("local_transportation", "car")
                    from src.tools.maps_tools import LOCAL_TRANSPORT_MAP
                    travel_mode = LOCAL_TRANSPORT_MAP.get(transport, "DRIVE")
                    from src.tools.itinerary_tools import _build_distance_matrix
                    distance_matrix = await _build_distance_matrix(locations, travel_mode)
                    if distance_matrix:
                        new_distance_pairs = build_symmetric_distance_pairs(locations, distance_matrix)
                        cached_pipeline["distance_pairs"] = new_distance_pairs
                        logger.info(f"🏨 [SELECT_APPLY] Distance matrix updated: {len(new_distance_pairs)} pairs")
            except Exception as e:
                logger.error(f"🏨 [SELECT_APPLY] Distance matrix recompute failed: {e}")

        cached_pipeline["schedule_constraints"] = schedule_constraints
        existing_itinerary["_cached_pipeline"] = cached_pipeline
        existing_itinerary["resolved_places"] = resolved_places
        existing_itinerary["days"] = existing_days
        current_plan["itinerary"] = existing_itinerary

        auto_msg = " ".join(auto_msgs) + " Update hotel names in all related stops. You MUST completely re-evaluate and holistically re-pace the affected days to ensure a natural flow based on the new check-in/check-out times. Preserve existing activities as much as possible. ONLY add minor filler activities if there is a large gap, or drop non-essential activities if time is cut short. Handle luggage logistics. Keep unaffected days unchanged."

        constraint_overrides.update({
            "type": "hotel",
            "hotel_name": last_hotel_name,
            "hotel_placeId": last_hotel_placeId,
            "needs_rerange": True,
            "auto_user_message": auto_msg,
        })

        return {
            "current_plan": current_plan,
            "constraint_overrides": constraint_overrides,
            "agent_outputs": {
                "hotel_agent": current_plan["hotel_search"],
                **({"restaurant_agent": current_plan["restaurant_search"]} if current_plan.get("restaurant_search") else {}),
            },
            "intent_output": {"intent": "select_hotel"},

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
            "intent_output": {"intent": "select_flight"},
            "final_response": msg,

        }

    flight_search = current_plan.get("flight_search", {})
    if not flight_search:
        logger.warning("✈️ [SELECT_APPLY] No flight_search results in current_plan")
        msg = "Chưa có kết quả tìm kiếm chuyến bay. Hãy tìm kiếm trước." if language == "vi" else "No flight search results available. Please search first."
        return {
            "current_plan": current_plan,
            "final_response": msg,

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

        }

    existing_outbound = flight_search.get("recommend_outbound_flight") or {}
    existing_return = flight_search.get("recommend_return_flight") or {}
    
    outbound = match.get("outbound") or existing_outbound
    return_flight = match.get("return") or existing_return
    
    total_price = 0
    if flight_search.get("type") == "round_trip":
        # round_trip must have both bundled, LLM returns total price.
        total_price = match.get("totalPrice") or flight_search.get("totalPrice", 0)
    else:
        # one_way, prices are separate
        if outbound:
            total_price += outbound.get("price", 0)
        if return_flight:
            total_price += return_flight.get("price", 0)

    logger.info(
        f"✈️ [SELECT_APPLY] Final selected flight: "
        f"outbound={outbound.get('flight_number', '?')}, "
        f"return={return_flight.get('flight_number', '?')} "
        f"(Total: {total_price})"
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

        auto_msg = (
            f"Flight changed. {outbound_info}. {return_info}. "
            f"This drastically changes the available time on the arrival and departure days. You MUST completely re-evaluate and holistically re-pace the schedules for these affected days to ensure a natural flow. "
            f"Preserve existing activities as much as possible. ONLY add minor filler activities if there is a large gap, or drop non-essential activities if time is cut short. Handle luggage logistics (e.g. early drop-off if arriving early). Keep unaffected days unchanged."
        )

        constraint_overrides.update({
            "type": "flight",
            "needs_rerange": True,
            "auto_user_message": auto_msg,
            "flight_agent_data": flight_agent_data,
        })

        return {
            "current_plan": current_plan,
            "constraint_overrides": constraint_overrides,
            "agent_outputs": {
                "flight_agent": flight_agent_data,
                # Preserve restaurant data so Synthesize can re-merge it into the updated itinerary
                **({"restaurant_agent": current_plan["restaurant_search"]} if current_plan.get("restaurant_search") else {}),
            },
            "intent_output": {"intent": "select_flight"},

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
            "intent_output": {"intent": "select_restaurant"},
            "final_response": msg,

        }

    restaurant_search = current_plan.get("restaurant_search", {})
    if not restaurant_search or not restaurant_search.get("meals"):
        msg = "Chưa có kết quả tìm kiếm quán ăn." if language == "vi" else "No restaurant search results available."
        return {
            "current_plan": current_plan,
            "final_response": msg,

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
                "constraint_overrides": {"type": "restaurant", "needs_rerange": False},
                "intent_output": {"intent": "select_restaurant"},
                "agent_outputs": {"itinerary_agent": itinerary},

            }

    # If could not apply to itinerary (e.g. standalone search without itinerary, or slot not found)
    msg = "Đã xảy ra lỗi hệ thống: Không thể áp dụng quán ăn này vào lịch trình của bạn. Vui lòng thử lại." if language == "vi" else "System error: Could not apply this restaurant to your itinerary. Please try again."
    return {
        "current_plan": current_plan,
        "constraint_overrides": {"type": "restaurant", "needs_rerange": False},
        "intent_output": {"intent": "select_restaurant"},
        "final_response": msg,

    }
