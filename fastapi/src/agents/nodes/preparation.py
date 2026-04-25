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
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.tools.search_tools import tavily_search
from src.config import settings

logger = logging.getLogger(__name__)

llm_preparation = (
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
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_PREPARATION or settings.GOOGLE_GEMINI_API_KEY,
        temperature=0.3,
        streaming=False,
    )
)

PREPARATION_AGENT_SYSTEM = """You are the Preparation Agent for a travel planning system.

You handle: budget estimation, packing suggestions, and practical travel notes.

## Input
You receive:
1. Full trip plan_context (destination, dates, travelers, budget, travel mode, pace, mobility plan)
2. Daily weather forecast (pre-fetched, per-day temperature and conditions)
3. Itinerary summary (which places are visited each day — use this for transport cost estimation, place-specific packing advice, and practical notes)

{budget_section}

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

The example below shows ALL possible budget type values. You MUST ONLY use the types listed in the Budget Categories section above. Include entries for EVERY category listed there.

{
  "budget": {
    "currency": "VND",
    "breakdown": [
      {"type": "Transport", "name": "describe item", "amount": 0, "details": "cost × quantity breakdown"},
      {"type": "Food & Drinks", "name": "describe item", "amount": 0, "details": "cost × quantity breakdown"},
      {"type": "Shopping", "name": "describe item", "amount": 0, "details": "cost × quantity breakdown"},
      {"type": "Activities", "name": "describe item", "amount": 0, "details": "cost × quantity breakdown"},
      {"type": "Other", "name": "describe item", "amount": 0, "details": "cost × quantity breakdown"},
      {"type": "Flight", "name": "describe item", "amount": 0, "details": "cost/person × num_travelers"},
      {"type": "Departure Transport", "name": "describe item", "amount": 0, "details": "cost/person × num_travelers"},
      {"type": "Accommodation", "name": "describe item", "amount": 0, "details": "cost/night × num_nights"},
      {"type": "Meals", "name": "describe item", "amount": 0, "details": "cost/meal × meals/day × num_days × num_travelers"}
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
- Budget: use ONLY the budget categories listed in the Budget Categories section above. Do NOT invent new type values.
- Budget amounts are for the ENTIRE trip duration (all days combined), NOT per-day
- Budget amounts MUST account for ALL travelers (multiply by number of people). The "details" field MUST show the full calculation: unit cost × quantity × num_travelers × num_days (where applicable). Example: "~200k/meal × 2 meals/day × 4 days × 2 people = 3,200,000"
- Multiple entries CAN share the same "type" — split by specific cost item (e.g., 2 separate "Transport" entries for taxi vs metro)
- Use the itinerary to reason about transport costs (more stops/farther apart → higher cost)
- Use the itinerary to give place-specific packing and note advice
- Packing list should reflect ACTUAL weather forecast + specific places being visited
- Consider number of travelers, children/infants, pace, travel mode, and local transport
- Be practical and specific to the destination
- If weather data notes some days are outside forecast range, mention this in weather_summary
"""

def _extract_itinerary_summary(itinerary_data: dict) -> list[dict]:
    """Extract a simplified itinerary summary for the Preparation Agent.

    Shows day → list of place names with roles, including hotel (start/end day).
    """
    summary = []
    for day_data in itinerary_data.get("days", []):
        day_idx = day_data.get("day", 1)
        places = []
        for stop in day_data.get("stops", []):
            raw_role = stop.get("role", [])
            roles = set(raw_role) if isinstance(raw_role, list) else {raw_role} if isinstance(raw_role, str) else set()
            name = stop.get("name", "")

            # Simplify hotel boundary roles
            if roles & {"start_day", "end_day"}:
                places.append({"name": name, "role": "hotel"})
            else:
                primary = sorted(roles)[0] if roles else ""
                places.append({"name": name, "role": primary})
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

    plan = state.get("macro_plan", {})
    current_plan = state.get("current_plan", {})
    plan_context = current_plan.get("plan_context", {})
    agent_outputs = state.get("agent_outputs", {})

    if plan.get("task_list"):
        logger.info("🎒 [PREPARATION_AGENT] Mode: PIPELINE")
    else:
        logger.info("🎒 [PREPARATION_AGENT] Mode: STANDALONE")

    destination = plan_context.get("destination", "")
    if not destination:
        logger.info("   No destination → skip")
        return {
            "agent_outputs": {"preparation_agent": {"skipped": True}},

        }

    preparation_result = {}

    try:
        # ── Check for MODIFY mode ─────────────────────────────────────
        # If current_plan already has preparation data, this is a modification
        existing_budget = current_plan.get("budget")
        existing_packing = current_plan.get("packing")
        existing_notes = current_plan.get("notes")
        is_modify = bool(existing_budget or existing_packing or existing_notes)

        # Get the user's latest message for context
        user_message = state.get("user_message", "")
        if user_message and user_message.startswith("["):
            user_message = ""

        if is_modify and user_message:
            # ═══ MODIFY MODE — adjust previous output ═══
            logger.info("🎒 [PREPARATION_AGENT] Mode: MODIFY (correcting previous output)")

            previous_output = {}
            if existing_budget:
                previous_output["budget"] = existing_budget
            if existing_packing:
                previous_output["packing"] = existing_packing
            if existing_notes:
                previous_output["notes"] = existing_notes

            modify_prompt = f"""You are the Preparation Agent. You previously generated the following output for this trip:

## Your Previous Output
{json.dumps(previous_output, indent=2, ensure_ascii=False)}

## Trip Context
{json.dumps(plan_context, indent=2, ensure_ascii=False)}

## User's Feedback
The user has a correction or adjustment to make:
"{user_message}"

## Instructions
- Carefully read the user's feedback and understand what they want changed.
- Modify ONLY the relevant parts of your previous output.
- Keep everything else unchanged.
- Return the COMPLETE updated JSON with all sections (budget, packing, notes) — even the unchanged ones.
- Respond in the same language as the user.
- Return ONLY valid JSON, no text before or after.
"""
            llm_messages = [
                SystemMessage(content=PREPARATION_AGENT_SYSTEM),
                HumanMessage(content=modify_prompt),
            ]

            result, tool_logs = await _run_agent_with_tools(
                llm=llm_preparation, messages=llm_messages,
                tools=[tavily_search], max_iterations=2,
                agent_name="PREPARATION_AGENT_MODIFY",
            )
            preparation_result = _extract_json(result.content)
            preparation_result["tools"] = tool_logs
            preparation_result["mode"] = "modify"

        else:
            # ═══ FRESH MODE — generate from scratch ═══
            logger.info("🎒 [PREPARATION_AGENT] Mode: FRESH (generating new)")

            # ── Step 1: Get weather data (pre-fetched by weather node) ────
            weather_data = agent_outputs.get("weather", {})
            if weather_data and weather_data.get("daily"):
                logger.info(f"🎒 [PREPARATION_AGENT] Using pre-fetched weather: {weather_data.get('covered_days', 0)} days")
            else:
                # Fallback: fetch ourselves if weather node didn't run
                logger.info("🎒 [PREPARATION_AGENT] No pre-fetched weather, fetching...")
                from src.agents.nodes.weather_fetch import _fetch_weather_for_trip
                weather_data = await _fetch_weather_for_trip(
                    destination=destination,
                    start_date_str=plan_context.get("start_date", ""),
                    end_date_str=plan_context.get("end_date", ""),
                )

            # ── Step 2: Extract itinerary summary ────────────────────────
            itinerary_data = agent_outputs.get("itinerary_agent", {})
            itinerary_summary = _extract_itinerary_summary(itinerary_data)
            logger.info(f"🎒 [PREPARATION_AGENT] Itinerary: {len(itinerary_summary)} days extracted")

            # ── Step 3: Build FULLY DYNAMIC budget prompt ────────────────
            # Determine which costs OTHER agents handle (or will handle)
            # Check 3 sources: intent_output, current_plan data, agent_outputs
            user_intent = (state.get("intent_output") or {}).get("intent", "")

            flight_data = agent_outputs.get("flight_agent", {})
            hotel_data = agent_outputs.get("hotel_agent", {})
            attraction_data = agent_outputs.get("attraction_agent", {})

            # Departure transport: Preparation ALWAYS handles this EXCEPT when Flight Agent ran.
            # Flight Agent = air travel specifically. All other transport (bus, train, car) = Preparation.
            # mobility_plan provides context (route, estimated cost) but doesn't "handle" the budget.
            flight_ran = (
                (bool(flight_data) and not flight_data.get("skipped", False))
                or bool(current_plan.get("flight_search"))
            )
            hotel_handled = (bool(hotel_data) and not hotel_data.get("skipped", False)) or bool(current_plan.get("selected_hotel"))
            attraction_handled = (bool(attraction_data) and not attraction_data.get("skipped", False))
            # Restaurant: check BOTH parallel execution (full_plan intent) AND existing data
            restaurant_handled = (
                user_intent == "full_plan"  # Restaurant runs in parallel with us
                or bool(current_plan.get("restaurant_search"))  # Already has restaurant data
                or (bool(agent_outputs.get("restaurant_agent", {})) and not agent_outputs.get("restaurant_agent", {}).get("skipped", False))
            )

            logger.info(f"🎒 [PREPARATION_AGENT] Agent coverage: flight_ran={flight_ran}, hotel={hotel_handled}, attraction={attraction_handled}, restaurant={restaurant_handled} (intent={user_intent})")

            # Build exclusion list (what to skip)
            excluded = []
            if flight_ran:
                excluded.append("Flight costs (handled by Flight Agent)")
            if hotel_handled:
                excluded.append("Hotel/accommodation costs (handled by Hotel Agent)")
            if attraction_handled:
                excluded.append("Attraction entry fees (handled by Attraction Agent)")
            if restaurant_handled:
                excluded.append("Restaurant/main meal costs (handled by Restaurant Agent)")

            # Build standard categories
            categories = []
            if restaurant_handled:
                categories.append('- "Food & Drinks" — ONLY small incidental expenses: coffee, bottled water, street snacks eaten BETWEEN main meals. Keep amounts LOW. Main meal costs are handled by the Restaurant Agent.')
            else:
                categories.append('- "Meals" — estimate main meal costs (breakfast, lunch, dinner) for all travelers per day')
                categories.append('- "Food & Drinks" — coffee, bottled water, street snacks eaten between main meals')
            if not flight_ran:
                # Preparation handles departure/return costs when Flight Agent didn't run
                # Check mobility_plan to determine if user is flying or using ground transport
                plan = state.get("macro_plan", {})
                dep_mode = plan.get("mobility_plan", {}).get("departure_logistics", {}).get("mode", "")
                if dep_mode == "flight":
                    categories.append('- "Flight" — estimate round-trip or one-way flight cost for all travelers')
                else:
                    categories.append('- "Departure Transport" — estimate departure/return transport cost for all travelers (bus, train, car, tolls, fuel, etc.)')
            categories.append('- "Transport" — LOCAL transportation only (taxi/Grab, bus, metro between attractions)')
            if not attraction_handled:
                categories.append('- "Attractions" — estimate entrance fees for attractions')
            categories.append('- "Activities" — minor entry fees, parking, bike rentals, boat rides, or activities not covered by Attraction Agent')
            categories.append('- "Shopping" — souvenirs, gifts, local products')
            categories.append('- "Other" — SIM card, internet, tips, contingency, any miscellaneous expenses')
            if not hotel_handled:
                categories.append('- "Accommodation" — estimate hotel/accommodation cost per night')

            # Build the budget section
            budget_section = "## Budget Estimation\n"
            if excluded:
                budget_section += "Do NOT include:\n"
                budget_section += "\n".join(f"- ❌ {e}" for e in excluded)
                budget_section += "\n\n"
            budget_section += "## Budget Categories — MUST use these exact \"type\" values:\n"
            budget_section += "\n".join(categories)
            budget_section += "\nNOTE: Do NOT use type values other than those listed above."

            system_content = PREPARATION_AGENT_SYSTEM.replace("{budget_section}", budget_section)
            logger.info(f"🎒 [PREPARATION_AGENT] Dynamic budget: excluded={len(excluded)}, categories={len(categories)}")

            # ── Step 4: Build context for LLM ────────────────────────────
            human_content = f"""## Trip Context
{json.dumps(plan_context, indent=2, ensure_ascii=False)}

## Daily Weather Forecast
{json.dumps(weather_data, indent=2, ensure_ascii=False)}

## Itinerary Summary (places per day)
{json.dumps(itinerary_summary, indent=2, ensure_ascii=False)}

Based on ALL the context above:
1. Estimate budget items using ONLY the budget categories specified in your instructions
2. Create a packing list based on weather + specific places visited (e.g., temple dress codes, outdoor sun protection)
3. Write practical travel notes with place-specific advice for {destination}

You may use tavily_search if you need specific local tips or customs info."""

            llm_messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=human_content),
            ]

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

    if "tools" in preparation_result:
        preparation_result.pop("tools", None)

    return {
        "agent_outputs": {"preparation_agent": preparation_result},

    }
