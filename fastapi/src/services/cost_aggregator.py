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
            if stop.get("role") == "attraction":
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
        if outbound:
            flight_number = outbound.get("flight_number", "")
            dep = outbound.get("departure_airport_name", "")
            arr = outbound.get("arrival_airport_name", "")
            flight_items.append({
                "name": f"{flight_number} ({dep} → {arr})",
                "amount": total_price if not return_f else 0,
                "note": "Chuyến bay đi (giá đã được gộp)" if return_f else "Chuyến bay đi"
            })
        if return_f:
            flight_number = return_f.get("flight_number", "")
            dep = return_f.get("departure_airport_name", "")
            arr = return_f.get("arrival_airport_name", "")
            flight_items.append({
                "name": f"{flight_number} ({dep} → {arr})",
                "amount": total_price if outbound else total_price,
                "note": "Chuyến bay về (tổng giá vé)" if outbound else "Chuyến bay về"
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
                        "name": f"  └ {inc_name}",
                        "amount": inc_total,
                        "note": inc_note,
                    })
                    attraction_subtotal += inc_total
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
        for meal in restaurant_data.get("meals", []):
            name = meal.get("name", "")
            cost = meal.get("estimated_cost_total", 0)
            day = meal.get("day", 0)
            meal_type = meal.get("meal_type", "")
            note = meal.get("note", "")
            restaurant_items.append({
                "name": f"{name} (Day {day} {meal_type})",
                "amount": cost,
                "note": note,
            })
            restaurant_subtotal += cost
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
    # ── Grand total ──────────────────────────────────────────────────
    result["grand_total"] = sum(
        cat.get("subtotal", 0) for cat in result["categories"].values()
    )
    logger.info(
        f"💰 [COST_AGGREGATOR] Categories: {list(result['categories'].keys())}, "
        f"Grand total: {result['grand_total']:,.0f} {currency}"
    )
    return result
