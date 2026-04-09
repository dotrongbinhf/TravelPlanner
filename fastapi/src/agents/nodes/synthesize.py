import copy
import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from src.agents.state import GraphState
from src.services.cost_aggregator import aggregate_all_costs
from src.services.apply_data_builder import build_apply_data
from src.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
logger = logging.getLogger(__name__)

llm_synthesize = (
    ChatOpenAI(
        model="google/gemini-3.1-flash-lite-preview",
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=True,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview",
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_SYNTHESIZE,
        temperature=0.3,
        streaming=True,
    )
)

SYNTHESIZE_SYSTEM = """You are the Synthesize Agent for a travel planning system.
Your job is to compile ALL the provided specialist agent data into a cohesive, engaging, and comprehensive travel plan.

## Persona & Tone
- Act as an intelligent, conversational AI travel assistant.
- Use a natural, friendly tone. Avoid overly formal or robotic phrasing (e.g., do NOT say "Chào mừng quý khách", "I have compiled data from experts", "Dear customer").
- Start directly with a warm, concise opening that addresses the user's specific trip.
- Do not hallucinate details not present in the data.
- Write the ENTIRE response in the language specified in "User Language".

## Formatting Instructions
- **MARKDOWN FORMATTING**: Use `##`, `###` headings, **bold** for names/prices/times, *italics* for notes, blockquotes `>` for tips, and lots of relevant emojis 🌴✈️🍲 to make it vibrant.
- Do NOT output raw JSON. Weave data naturally into prose.

## Required Sections — IN THIS ORDER (skip those with no data):
**IMPORTANT**: Number sections SEQUENTIALLY starting from 1. If a section is skipped (e.g., no flight data), do NOT leave a gap in numbering. For example, if there are no Flights and no Hotels, the order would be: 1. Trip Overview → 2. Weather → 3. Daily Itinerary → 4. Budget → ...

### 🗺️ Trip Overview
Brief summary: destination, dates, number of travelers, trip style/pace.

### 🌤️ Weather & Climate
- Immediately after Trip Overview, summarize what the weather will be like during the trip dates.
- Provide an OVERALL weather paragraph first (general conditions, what to expect).
- Then provide a DAILY breakdown: for each day, state the date, day of week, condition, temperature range, rain chance.
- Weave this into practical advice (e.g., "Day 2 may have afternoon showers — consider indoor activities or carry an umbrella").

### ✈️ Flights
- Show the RECOMMENDED outbound and return flights with: flight number, airline, departure/arrival times, price.
- If a booking **link** is provided, use natural phrasing and make the link visually prominent. Do NOT just display the raw URL.
- For round-trip bookings, only one link is needed (the outbound link covers both legs).
- For one-way bookings, show separate links for each leg.
- Then list 2-3 **Alternative Flights** (from the `alternatives` array) with: flight number, route, departure time, price, link.

### 🏨 Accommodation
- Show the recommended hotel: name, check-in/out dates, total rate, why it was chosen. Note: Only output the actual hotel name, do NOT prefix or append the `segment_name` to it.
- If a booking **link** is provided, use natural phrasing and make the link visually prominent. Do NOT just display the raw URL.
- Then list 2-3 **Alternative Hotels** (from `alternatives`) with: name, rating, total rate, link.

### 📅 Daily Itinerary
- Detailed day-by-day, step-by-step breakdown.
- **Day numbering MUST start from Day 1** (not Day 0). The itinerary data uses 0-indexed days internally, but your output should show "Ngày 1" / "Day 1", "Ngày 2" / "Day 2", etc.
- Each day's heading MUST use the `title` field from the itinerary data exactly as provided (e.g., "## Ngày 1: Khám phá phố cổ Hà Nội").
- Include times, places, activities, and transport between stops.
- For each MEAL (which will have `restaurant_details` embedded in the schedule): state the recommended restaurant name, estimated cost. Then casually suggest alternative restaurants in a natural tone.
- For attractions: mention any "includes" (sub-attractions) they will visit.

### 💰 Budget Breakdown
- Summarize expenses by category (Flights, Accommodation, Attractions, Restaurants, Other).
- Show the Grand Total in the trip currency.
- Use the AGGREGATED BUDGET data provided.

### 🎒 Packing List
- What to bring based on weather forecasts and planned activities.
- Be specific and practical.
- Use simple bullet list format (- item).

### 📝 Travel Notes
- Important tips, safety info, local customs, useful phrases.
- Must be a SEPARATE section from Packing List — do NOT merge them.
- Use simple bullet lists (- item), same format as Packing List. Do NOT use blockquotes (`>`) or *italics* for list items in this section.

## Rules
- Use emoji in section headers
- Include specific times, prices, and ratings wherever available
- For simple queries (greetings), respond naturally without the full template
- Highlight top recommendations
- Be detailed — explain *why* something is recommended
"""


def _build_curated_context(agent_outputs: dict, plan_context: dict, aggregated_costs: dict) -> str:
    """Build a curated context string with ONLY the fields Synthesize needs.
    No raw dumps, no tool logs, no resolved_places, no distance matrices."""
    language = plan_context.get("language", "en")
    parts = [
        f"--- USER LANGUAGE ---\nLanguage Code: {language}\n",
    ]

    # Plan context — only essential trip info
    ctx = {
        "departure": plan_context.get("departure"),
        "destination": plan_context.get("destination"),
        "start_date": plan_context.get("start_date"),
        "end_date": plan_context.get("end_date"),
        "num_days": plan_context.get("num_days"),
        "adults": plan_context.get("adults"),
        "children": plan_context.get("children"),
        "infants": plan_context.get("infants"),
        "pace": plan_context.get("pace"),
        "budget_level": plan_context.get("budget_level"),
        "currency": plan_context.get("currency"),
    }
    # Include mobility plan overview (high-level trip description)
    mobility = plan_context.get("mobility_plan") or {}
    if mobility.get("overview"):
        ctx["trip_overview"] = mobility["overview"]
    parts.append(f"--- PLAN CONTEXT ---\n{json.dumps(ctx, ensure_ascii=False, indent=2)}\n")

    # Aggregated budget (already curated by cost_aggregator)
    parts.append(f"--- AGGREGATED BUDGET ---\n{json.dumps(aggregated_costs, ensure_ascii=False, indent=2)}\n")

    # Flight — recommended flights (with google_flights_url) + total price + alternatives
    flight = agent_outputs.get("flight_agent", {})
    if flight and not flight.get("skipped"):
        flight_type = flight.get("type", "one_way")
        curated_flight = {
            "type": flight_type,
            "totalPrice": flight.get("totalPrice", 0),
        }
        
        # Top-level google_flights_url (for roundtrip/single direction)
        if flight.get("google_flights_url"):
            curated_flight["google_flights_url"] = flight["google_flights_url"]
        
        # Outbound flight
        outbound = flight.get("recommend_outbound_flight")
        if outbound:
            curated_flight["recommend_outbound_flight"] = {
                k: v for k, v in outbound.items()
                if k not in ("departure_token", "_raw") and not k.startswith("_")
            }
        if flight.get("recommend_outbound_note"):
            curated_flight["recommend_outbound_note"] = flight["recommend_outbound_note"]
        
        # Return flight
        ret = flight.get("recommend_return_flight")
        if ret:
            curated_flight["recommend_return_flight"] = {
                k: v for k, v in ret.items()
                if k not in ("departure_token", "_raw") and not k.startswith("_")
            }
        if flight.get("recommend_return_note"):
            curated_flight["recommend_return_note"] = flight["recommend_return_note"]
        
        # Alternatives
        if flight.get("alternatives"):
            curated_flight["alternatives"] = flight["alternatives"]
        
        parts.append(f"--- FLIGHTS ---\n{json.dumps(curated_flight, ensure_ascii=False, indent=2)}\n")

    # Hotel — name, rate, dates, link, alternatives per segment
    hotel = agent_outputs.get("hotel_agent", {})
    if hotel and not hotel.get("skipped"):
        curated_segments = []
        for seg in hotel.get("segments", []):
            curated_segments.append({
                "segment_name": seg.get("segment_name"),
                "recommend_hotel_name": seg.get("recommend_hotel_name"),
                "totalRate": seg.get("totalRate"),
                "check_in": seg.get("check_in"),
                "check_out": seg.get("check_out"),
                "recommend_note": seg.get("recommend_note", ""),
                "link": seg.get("link", ""),
                "alternatives": seg.get("alternatives", []),
            })
        parts.append(f"--- HOTELS ---\n{json.dumps(curated_segments, ensure_ascii=False, indent=2)}\n")

    # Itinerary — full days structure (this IS the core output)
    itinerary = agent_outputs.get("itinerary_agent", {})
    if itinerary and not itinerary.get("error"):
        curated_days = copy.deepcopy(itinerary.get("days", []))
        
        # Merge Restaurant info into the itinerary
        restaurant = agent_outputs.get("restaurant_agent", {})
        if restaurant and not restaurant.get("skipped"):
            for meal in restaurant.get("meals", []):
                m_day = meal.get("day")
                m_type = meal.get("meal_type")
                for d in curated_days:
                    if d.get("day") == m_day:
                        for stop in d.get("stops", []):
                            roles = stop.get("role", [])
                            if isinstance(roles, str):
                                roles = [roles]
                            if m_type in roles:
                                stop["restaurant_details"] = {
                                    "name": meal.get("name"),
                                    "estimated_cost_total": meal.get("estimated_cost_total"),
                                    "alternatives": meal.get("alternatives", []),
                                }
        
        # Clean up unnecessary fields from stops for the LLM
        for d in curated_days:
            for stop in d.get("stops", []):
                stop.pop("placeId", None)
                stop.pop("_raw", None)
                stop.pop("departure_token", None)
                
        curated_itinerary = {
            "days": curated_days,
            "dropped": itinerary.get("dropped", []),
        }
        parts.append(f"--- DAILY ITINERARY ---\n{json.dumps(curated_itinerary, ensure_ascii=False, indent=2)}\n")

    # Weather — curated daily forecast
    weather = agent_outputs.get("weather", {})
    if weather and not weather.get("skipped"):
        curated_weather = {
            "daily": weather.get("daily", []),
            "covered_days": weather.get("covered_days", 0),
            "total_trip_days": weather.get("total_trip_days", 0),
        }
        if weather.get("outside_range_note"):
            curated_weather["note"] = weather["outside_range_note"]
        parts.append(f"--- WEATHER ---\n{json.dumps(curated_weather, ensure_ascii=False, indent=2)}\n")

    # Preparation — budget breakdown, packing, notes
    prep = agent_outputs.get("preparation_agent", {})
    if prep and not prep.get("skipped"):
        curated_prep = {
            "budget": prep.get("budget", {}),
            "packing_lists": prep.get("packing_lists", []),
            "notes": prep.get("notes", []),
        }
        parts.append(f"--- PREPARATION ---\n{json.dumps(curated_prep, ensure_ascii=False, indent=2)}\n")

    return "\n".join(parts)


async def synthesize_agent_node(state: GraphState) -> dict[str, Any]:
    """Synthesize Agent — Compiles curated agent data and aggregated costs into final response."""
    logger.info("=" * 60)
    logger.info("📝 [SYNTHESIZE] Node entered")
    agent_outputs = state.get("agent_outputs", {})
    plan = state.get("orchestrator_plan", {})
    intent = plan.get("intent", "greeting")
    plan_context = plan.get("plan_context", {})

    is_simple = intent in ("greeting", "information_query", "clarification_needed", "general") or not plan_context
    system_content = SYNTHESIZE_SYSTEM
    aggregated_costs = {}

    if is_simple:
        system_content += "\n\nThis is a simple query/greeting. Respond naturally to the user in their language without outputting a full travel plan template."
        structured_output = {}
    else:
        # 1. Aggregate Costs
        logger.info("   Aggregating costs...")
        aggregated_costs = aggregate_all_costs(agent_outputs, plan_context)

        # 2. Build curated context — only fields Synthesize actually needs
        context_str = _build_curated_context(agent_outputs, plan_context, aggregated_costs)
        system_content += f"\n\n## Agent Data for Synthesis:\n{context_str}"

        logger.info(f"   Curated context size: {len(context_str):,} chars")

    # Build LLM messages — only system prompt + one user message
    llm_messages = [SystemMessage(content=system_content)]

    # Find the original user request from messages
    messages = state.get("messages", [])
    user_request = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = msg.content if hasattr(msg, "content") else str(msg)
            if not content.startswith("["):
                user_request = content
                break
    llm_messages.append(HumanMessage(content=user_request or "Please provide my travel plan."))

    try:
        logger.info("   Invoking LLM for synthesis...")
        result = await llm_synthesize.ainvoke(llm_messages)

        raw_resp = result.content
        if isinstance(raw_resp, list):
            text_parts = []
            for part in raw_resp:
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
                elif isinstance(part, str):
                    text_parts.append(part)
            final_response = "".join(text_parts)
        else:
            final_response = str(raw_resp)

    except Exception as e:
        logger.error(f"   ❌ Synthesize error: {e}", exc_info=True)
        final_response = "Sorry, an error occurred while generating your travel plan. Please try again."

    # Build structured output for frontend
    db_commands = []
    structured_output = {"intent": intent}
    if not is_simple:
        structured_output["plan_context"] = plan_context
        structured_output["aggregated_costs"] = aggregated_costs

        if "itinerary_agent" in agent_outputs:
            structured_output["itinerary"] = agent_outputs["itinerary_agent"]
        if "flight_agent" in agent_outputs:
            structured_output["flights"] = agent_outputs["flight_agent"]
        if "hotel_agent" in agent_outputs:
            structured_output["hotels"] = agent_outputs["hotel_agent"]
        if "restaurant_agent" in agent_outputs:
            structured_output["restaurants"] = agent_outputs["restaurant_agent"]
        if "preparation_agent" in agent_outputs:
            prep = agent_outputs["preparation_agent"]
            structured_output["budget"] = prep.get("budget", {})
            structured_output["packing_lists"] = prep.get("packing_lists", [])
            structured_output["notes"] = prep.get("notes", [])
            structured_output["preparation"] = prep
        if "itinerary_agent" in agent_outputs:
            structured_output["daily_schedules"] = agent_outputs["itinerary_agent"].get("daily_schedules", [])

        # Build normalized apply_data for frontend → .NET Apply endpoint
        try:
            apply_data = build_apply_data(agent_outputs, plan_context, aggregated_costs)
            structured_output["apply_data"] = apply_data
        except Exception as e:
            logger.error(f"   ❌ Failed to build apply_data: {e}", exc_info=True)
            structured_output["apply_data"] = None

    logger.info("📝 [SYNTHESIZE] Node completed")
    logger.info("=" * 60)
    return {
        "final_response": final_response,
        "structured_output": structured_output,
        "db_commands": db_commands,
        "messages": [AIMessage(content=final_response)],
    }