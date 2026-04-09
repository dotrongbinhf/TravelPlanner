"""
Cost Aggregator Service.
Collects costs from all agent outputs and merges with Preparation Agent budget
to produce a unified cost breakdown for the Synthesize Agent.
Sources:
- Flight Agent: totalPrice per leg (outbound + return)
- Hotel Agent: totalRate per segment
- Attraction Agent: estimated_entrance_fee (main + includes), filtered by itinerary
- Restaurant Agent: estimated_cost_total per meal
- Preparation Agent: budget breakdown (other costs)
"""
import logging
from typing import Any
logger = logging.getLogger(__name__)
def _get_scheduled_attractions(itinerary_data: dict) -> dict[str, list[str]]:
    """Extract attraction names and their scheduled includes from itinerary output.
    Returns:
        Dict mapping attraction name → list of included sub-attraction names
        that were actually scheduled.
    """
    scheduled = {}
    for day_data in itinerary_data.get("days", []):
        for stop in day_data.get("stops", []):
            # Handle role as list (new format) or string (legacy)
            role = stop.get("role", [])
            roles = set(role) if isinstance(role, list) else {role} if isinstance(role, str) else set()
            if "attraction" in roles:
                name = stop.get("name", "")
                includes = stop.get("includes", [])
                if name:
                    scheduled[name] = includes
    return scheduled
def _find_attraction_data(
    name: str, attraction_output: dict
) -> dict | None:
    """Find attraction data by name across all segments."""
    for seg in attraction_output.get("segments", []):
        for attr in seg.get("attractions", []):
            if attr.get("name", "").lower() == name.lower():
                return attr
    return None
def aggregate_all_costs(
    agent_outputs: dict[str, Any],
    plan_context: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate costs from all agent outputs into a unified breakdown.
    Args:
        agent_outputs: Dict of all agent results keyed by agent name.
        plan_context: Plan context from orchestrator (currency, travelers, etc).
    Returns:
        Unified cost breakdown with categories, items, subtotals, and grand total.
    """
    currency = plan_context.get("currency", "VND")
    result = {
        "currency": currency,
        "categories": {},
        "grand_total": 0,
    }
    # ── 1. Flights ────────────────────────────────────────────────────
    flight_data = agent_outputs.get("flight_agent", {})
    flight_items = []
    flight_subtotal = 0
    if flight_data and not flight_data.get("skipped"):
        total_price = flight_data.get("totalPrice", 0)
        outbound = flight_data.get("recommend_outbound_flight")
        return_f = flight_data.get("recommend_return_flight")
        if outbound and return_f:
            # Round trip
            out_fn = outbound.get("flight_number", "")
            ret_fn = return_f.get("flight_number", "")
            flight_items.append({
                "name": f"{out_fn} ⇌ {ret_fn}",
                "amount": total_price,
            })
        else:
            # One way flights
            if outbound:
                flight_items.append({
                    "name": outbound.get("flight_number", "Outbound Flight"),
                    "amount": total_price,
                })
            elif return_f:
                flight_items.append({
                    "name": return_f.get("flight_number", "Return Flight"),
                    "amount": total_price,
                })
            
        flight_subtotal += total_price
    if flight_items:
        result["categories"]["flights"] = {
            "items": flight_items,
            "subtotal": flight_subtotal,
        }
    # ── 2. Accommodation ─────────────────────────────────────────────
    hotel_data = agent_outputs.get("hotel_agent", {})
    hotel_items = []
    hotel_subtotal = 0
    if hotel_data and not hotel_data.get("skipped"):
        for seg in hotel_data.get("segments", []):
            name = seg.get("recommend_hotel_name", "Hotel")
            total_rate = seg.get("totalRate", 0)
            ci = seg.get("check_in", "")
            co = seg.get("check_out", "")
            seg_name = seg.get("segment_name", "")
            note_parts = []
            if seg_name:
                note_parts.append(seg_name)
            if ci and co:
                note_parts.append(f"{ci} → {co}")
            hotel_items.append({
                "name": name,
                "amount": total_rate,
                "note": ", ".join(note_parts) if note_parts else "",
            })
            hotel_subtotal += total_rate
    if hotel_items:
        result["categories"]["accommodation"] = {
            "items": hotel_items,
            "subtotal": hotel_subtotal,
        }
    # ── 3. Attractions (only scheduled ones) ─────────────────────────
    itinerary_data = agent_outputs.get("itinerary_agent", {})
    attraction_data = agent_outputs.get("attraction_agent", {})
    attraction_items = []
    attraction_subtotal = 0
    if itinerary_data and attraction_data:
        scheduled = _get_scheduled_attractions(itinerary_data)
        
        for sched_name, sched_includes in scheduled.items():
            attr_info = _find_attraction_data(sched_name, attraction_data)
            if not attr_info:
                continue
            # Main attraction fee
            fee = attr_info.get("estimated_entrance_fee", {})
            main_total = fee.get("total", 0)
            main_note = fee.get("note", "")
            attraction_items.append({
                "name": sched_name,
                "amount": main_total,
                "note": main_note,
            })
            attraction_subtotal += main_total
            # Includes fees (only for sub-attractions that were scheduled)
            for inc in attr_info.get("includes", []):
                inc_name = inc.get("name", "")
                if inc_name and inc_name in sched_includes:
                    inc_fee = inc.get("estimated_entrance_fee", {})
                    inc_total = inc_fee.get("total", 0)
                    inc_note = inc_fee.get("note", "")
                    attraction_items.append({
                        "name": inc_name,
                        "amount": inc_total,
                        "note": inc_note,
                    })
                    attraction_subtotal += inc_total
    # If there are multiple attraction items, group them under a localized header
    if len(attraction_items) > 1:
        attr_group_name = "Phí tham quan" if plan_context.get("language") == "vi" else "Attraction Fees"
        for item in attraction_items:
            item["groupName"] = attr_group_name
    if attraction_items:
        result["categories"]["attractions"] = {
            "items": attraction_items,
            "subtotal": attraction_subtotal,
        }
    # ── 4. Restaurants ────────────────────────────────────────────────
    restaurant_data = agent_outputs.get("restaurant_agent", {})
    restaurant_items = []
    restaurant_subtotal = 0
    if restaurant_data and not restaurant_data.get("skipped"):
        is_vi = plan_context.get("language") == "vi"
        for meal in restaurant_data.get("meals", []):
            cost = meal.get("estimated_cost_total", 0)
            day = meal.get("day", 0)
            meal_type = meal.get("meal_type", "").capitalize()
            # If meal_type is breakfast, lunch, dinner -> translate if needed
            if is_vi:
                meal_transl = {"breakfast": "Sáng", "lunch": "Trưa", "dinner": "Tối"}
                mt_lower = meal_type.lower()
                meal_type = meal_transl.get(mt_lower, meal_type)
                
            day_prefix = "Ngày" if is_vi else "Day"
            
            restaurant_items.append({
                "name": f"{day_prefix} {day} - {meal_type}",
                "amount": cost,
            })
            restaurant_subtotal += cost
    # If multiple meals, group them under a localized header
    if len(restaurant_items) > 1:
        meal_group_name = "Các bữa ăn" if plan_context.get("language") == "vi" else "Meals"
        for item in restaurant_items:
            item["groupName"] = meal_group_name
    if restaurant_items:
        result["categories"]["restaurants"] = {
            "items": restaurant_items,
            "subtotal": restaurant_subtotal,
        }
    # ── 5. Other costs (from Preparation Agent) ───────────────────────
    prep_data = agent_outputs.get("preparation_agent", {})
    other_items = []
    other_subtotal = 0
    if prep_data and not prep_data.get("skipped"):
        budget = prep_data.get("budget", {})
        for item in budget.get("breakdown", []):
            item_type = item.get("type", "Other")
            name = item.get("name", "")
            amount = item.get("amount", 0)
            details = item.get("details", "")
            other_items.append({
                "name": f"[{item_type}] {name}",
                "amount": amount,
                "note": details,
            })
            other_subtotal += amount
    if other_items:
        result["categories"]["other"] = {
            "items": other_items,
            "subtotal": other_subtotal,
        }
    # ── 6. Transport costs (from mobility_plan) ──────────────────────
    mobility_plan = plan_context.get("mobility_plan") or {}
    dep_log = mobility_plan.get("departure_logistics") or {}
    ret_log = mobility_plan.get("return_logistics") or {}
    transport_items = []
    transport_subtotal = 0

    dep_mode = dep_log.get("mode", "")
    if dep_mode and dep_mode != "flight":
        dep_cost = dep_log.get("estimated_cost", 0)
        if isinstance(dep_cost, (int, float)) and dep_cost > 0:
            transport_items.append({
                "name": f"Di chuyển đi ({dep_mode})",
                "amount": dep_cost,
                "note": dep_log.get("estimated_cost_note", ""),
            })
            transport_subtotal += dep_cost

        ret_cost = ret_log.get("estimated_cost", 0)
        if isinstance(ret_cost, (int, float)) and ret_cost > 0:
            transport_items.append({
                "name": f"Di chuyển về ({ret_log.get('mode', dep_mode)})",
                "amount": ret_cost,
                "note": ret_log.get("estimated_cost_note", ""),
            })
            transport_subtotal += ret_cost

    if transport_items:
        result["categories"]["transport"] = {
            "items": transport_items,
            "subtotal": transport_subtotal,
        }
    # ── Grand total ──────────────────────────────────────────────────
    result["grand_total"] = sum(
        cat.get("subtotal", 0) for cat in result["categories"].values()
    )
    logger.info(
        f"💰 [COST_AGGREGATOR] Categories: {list(result['categories'].keys())}, "
        f"Grand total: {result['grand_total']:,.0f} {currency}"
    )
    return result
