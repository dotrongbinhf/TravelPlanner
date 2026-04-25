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
            # Ensure total_rate is numeric (it might be a string like "$120" or "1,200,000 VND")
            if isinstance(total_rate, str):
                import re
                digits = re.sub(r"[^\d.]", "", total_rate)
                total_rate = float(digits) if digits else 0
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
    attraction_subtotal = 0
    if itinerary_data and attraction_data:
        scheduled = _get_scheduled_attractions(itinerary_data)
        
        for sched_name, sched_includes in scheduled.items():
            attr_info = _find_attraction_data(sched_name, attraction_data)
            if not attr_info:
                continue
            # Main attraction fee
            fee = attr_info.get("estimated_entrance_fee", {})
            attraction_subtotal += fee.get("total", 0)
            # Includes fees (only for sub-attractions that were scheduled)
            for inc in attr_info.get("includes", []):
                inc_name = inc.get("name", "")
                if inc_name and inc_name in sched_includes:
                    inc_fee = inc.get("estimated_entrance_fee", {})
                    attraction_subtotal += inc_fee.get("total", 0)
    # Consolidate all attractions into a single item
    if attraction_subtotal > 0:
        is_vi = plan_context.get("language") == "vi"
        attr_label = "Vé tham quan" if is_vi else "Entrance Fees"
        result["categories"]["attractions"] = {
            "items": [{"name": attr_label, "amount": attraction_subtotal}],
            "subtotal": attraction_subtotal,
        }
    # ── 4. Restaurants ────────────────────────────────────────────────
    restaurant_data = agent_outputs.get("restaurant_agent", {})
    restaurant_subtotal = 0
    if restaurant_data and not restaurant_data.get("skipped"):
        for meal in restaurant_data.get("meals", []):
            cost = meal.get("estimated_cost_total", 0)
            restaurant_subtotal += cost
    # Consolidate all meals into a single item
    if restaurant_subtotal > 0:
        is_vi = plan_context.get("language") == "vi"
        meal_label = "Chi phí ăn uống" if is_vi else "Meal Costs"
        result["categories"]["restaurants"] = {
            "items": [{"name": meal_label, "amount": restaurant_subtotal}],
            "subtotal": restaurant_subtotal,
        }
    # ── 5. Other costs (from Preparation Agent) ───────────────────────
    # Preparation handles: departure transport, meals (when no Restaurant Agent),
    # accommodation (when no Hotel Agent), attractions (when no Attraction Agent)
    PREP_TYPE_TO_CATEGORY = {
        "Flight": "flights",
        "Departure Transport": "transport",
        "Accommodation": "accommodation",
        "Meals": "restaurants",
        "Attractions": "attractions",
        # Standard types stay in "other"
        "Food & Drinks": "other",
        "Transport": "other",
        "Activities": "other",
        "Shopping": "other",
        "Other": "other",
    }
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

            # Route to correct category
            target_category = PREP_TYPE_TO_CATEGORY.get(item_type, "other")

            # Check if we have real data for this category
            has_real_flight = bool(flight_items) and target_category == "flights"
            has_real_hotel = bool(hotel_items) and target_category == "accommodation"
            has_real_meals = bool(restaurant_subtotal > 0) and target_category == "restaurants"
            has_real_attr = bool(attraction_subtotal > 0) and target_category == "attractions"

            if has_real_flight or has_real_hotel or has_real_meals or has_real_attr:
                logger.info(f"💰 [COST_AGGREGATOR] Dropping preparation estimate for {item_type} because real data exists.")
                continue

            entry = {
                "name": f"[{item_type}] {name}" if target_category == "other" else name,
                "amount": amount,
                "note": details,
                "estimated": True,  # Flag as Preparation estimate
            }

            if target_category == "other":
                other_items.append(entry)
                other_subtotal += amount
            else:
                # Add to the correct category (create if doesn't exist)
                if target_category not in result["categories"]:
                    result["categories"][target_category] = {"items": [], "subtotal": 0}
                result["categories"][target_category]["items"].append(entry)
                result["categories"][target_category]["subtotal"] += amount

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
