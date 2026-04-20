import copy
import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from src.agents.state import GraphState
from src.services.cost_aggregator import aggregate_all_costs
from src.services.apply_data_builder import build_apply_data, build_sectioned_apply_data
from src.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
logger = logging.getLogger(__name__)

llm_synthesize = (
    ChatOpenAI(
        model=settings.MODEL_NAME,
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.1,
        streaming=True,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model=settings.MODEL_NAME,
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_SYNTHESIZE or settings.GOOGLE_GEMINI_API_KEY,
        temperature=0.1,
        streaming=True,
    )
)

SYNTHESIZE_SYSTEM = """You are the Synthesize Agent for a travel planning system.
Compile specialist agent data into a polished, visually-rich, and NEAT travel plan.

## Core Rules
- **ONLY output sections that have actual agent data.** If an agent did not run or has no data, SKIP that section entirely.
- **Do NOT hallucinate.** Never invent records.
- **Be CONCISE and ELEGANT.** Do NOT use dense paragraphs. Use short, punchy sentences.
- **Friendly & Natural Tone.** Act as a highly professional yet friendly AI travel assistant.
- Write the ENTIRE response in the language specified in "RESPONSE LANGUAGE".

## Visual Formatting — Clean, Spaced, and Scannable

### General Requirements
- Use `##` for main sections with fitting emojis, `###` for subsections.
- **Use Tables** where appropriate (e.g. Weather, Budget) to keep data structured.
- **Highlight (bold)** key names, times, and prices so they stand out clearly.
- Add plenty of breathing room: use line breaks to separate independent thoughts clearly.

### Trip Overview
One compact, welcoming paragraph highlighting destination, dates, travelers, and trip style.

### Weather & Climate
- 1-2 sentence overall summary.
- Daily forecast formatted as a **Markdown Table**:

| Date | Weather | Temperature | Rain |
|------|-----------|-----------|-----|
| 15/04 (Thứ 4) | ☀️ Nắng | 28-34°C | 10% |
| 16/04 (Thứ 5) | 🌦️ Mưa rào | 26-32°C | 60% |

- 1 practical tip below. If heavy rain or bad weather is forecasted on certain days, suggest rearranging the itinerary or adjusting outdoor plans to avoid those days.

### Flights
- CRITICAL: If there is no `--- FLIGHTS ---` data provided in the Agent Data block, you MUST NOT create a Flights section at all, and DO NOT output the `[FLIGHT_UI_WIDGET]` tag.
- If data exists, create a dedicated **Flights** section.
- Introduce the flights with a natural, engaging sentence.
- CRITICAL: Do NOT generate Markdown tables or bulleted lists for flight details.
- Instead, you MUST output exactly this placeholder tag on a new line: `[FLIGHT_UI_WIDGET]`
- The system will automatically inject beautiful Interactive Flight Cards in place of that tag.
- After the widget tag, you may add a brief note about booking links or next steps.

### Accommodation
- CRITICAL: If there is no `--- HOTELS ---` data provided in the Agent Data block, you MUST NOT create an Accommodation section at all, and DO NOT output the `[HOTEL_UI_WIDGET]` tag.
- If data exists, create a dedicated **Accommodation** section.
- Introduce the hotels with a natural, engaging sentence.
- CRITICAL: Do NOT generate Markdown tables or bulleted lists for hotel details.
- Instead, you MUST output exactly this placeholder tag on a new line: `[HOTEL_UI_WIDGET]`
- The system will automatically inject beautiful Interactive Hotel Cards in place of that tag.

### Daily Itinerary (CRITICAL FORMATTING)
- NEVER use blockquotes (`>`). NEVER use the clock emoji (`🕐`).
- Use **time ranges** like `**07:00 - 09:00**` to show start-end.
- **Highlight** all place/attraction names.
- Write naturally, fluidly, and beautifully — use a literary and engaging travelogue style ("văn vở", descriptive) to make the activities sound exciting. Do NOT use a rigid template or cold list.
- Weave the names of places and details seamlessly into paragraphs under each time block.
- If an attraction has `includes` (sub-attractions), weave ALL of them naturally into the description on the SAME LINE.
- Format example:

### Day 1: Exploring Hanoi
**07:00 - 08:30** 🛬 Touch down at Noi Bai Airport and enjoy a relaxing transfer to your hotel.
**09:00 - 11:00** 🏛️ Step back in time as you visit the striking **HO CHI MINH MAUSOLEUM**, before taking a peaceful stroll through the lush grounds of **HO CHI MINH'S STILT HOUSE**, the iconic **ONE PILLAR PAGODA**, and the grand **PRESIDENTIAL PALACE**.
**12:00 - 13:00** 🍜 Treat your taste buds to an unforgettable bowl of authentic Hanoi pho at the famous **PHO THIN**.
**14:00 - 15:30** 🌊 Soak in the poetic atmosphere of **HOAN KIEM LAKE** while meandering through the vibrant alleys of the Old Quarter.

### Budget Breakdown
- Use a **summary table** (columns: Category, Cost). Include a bold Total row.

### Packing List
- Clean, grouped bullet points (clothes, essentials, documents).

### Travel Notes
- Practical tips, cultural advice, and useful reminders as a separate bullet list.

### Closing & Next Steps
- End your response by asking if they want to modify the current result, or if they want to proceed with building the missing parts of their trip.
- Currently, the user has built: {built_sections_text}.
- Mention what is still missing (e.g. Accommodations, Attraction details, Budget analysis) and ask if they want you to work on those next.

## Section Order (skip missing sections)
1. Trip Overview → 2. Weather → 3. Budget → 4. Daily Itinerary → 5. Packing List → 6. Travel Notes → 7. Accommodation → 8. Flights

Note: Accommodation and Flights are placed LAST because they have rich interactive UI widgets that should cap off the response visually.
"""


def _build_curated_context(agent_outputs: dict, plan_context: dict, aggregated_costs: dict, mobility_plan: dict = None) -> str:
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
    mobility = mobility_plan or {}
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
                "recommend_note": seg.get("recommend_note", ""),
                "alternatives": [alt.get("name") for alt in seg.get("alternatives", [])]
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

    # Restaurant — standalone mode (when no itinerary to merge into)
    restaurant = agent_outputs.get("restaurant_agent", {})
    if restaurant and not restaurant.get("skipped") and not itinerary:
        curated_restaurant = {
            "meals": [
                {
                    "day": m.get("day"),
                    "meal_type": m.get("meal_type"),
                    "name": m.get("name"),
                    "place_id": m.get("place_id"),
                    "rating": m.get("rating"),
                    "user_ratings_total": m.get("user_ratings_total"),
                    "price_level": m.get("price_level"),
                    "note": m.get("note", m.get("justification", "")),
                    "estimated_cost_total": m.get("estimated_cost_total"),
                    "alternatives": [
                        (alt.get("name") if isinstance(alt, dict) else alt)
                        for alt in m.get("alternatives", [])
                    ],
                }
                for m in restaurant.get("meals", [])
            ],
        }
        parts.append(f"--- RESTAURANTS ---\n{json.dumps(curated_restaurant, ensure_ascii=False, indent=2)}\n")

    # Attraction — curated for standalone or pipeline
    attraction = agent_outputs.get("attraction_agent", {})
    if attraction and not attraction.get("skipped"):
        curated_segments = []
        for seg in attraction.get("segments", []):
            curated_attractions = []
            for attr in seg.get("attractions", []):
                curated_attractions.append({
                    "name": attr.get("name"),
                    "must_visit": attr.get("must_visit", False),
                    "notes": attr.get("notes", ""),
                    "estimated_entrance_fee": attr.get("estimated_entrance_fee"),
                    "includes": [inc.get("name") for inc in attr.get("includes", []) if isinstance(inc, dict)],
                })
            curated_segments.append({
                "segment_name": seg.get("segment_name"),
                "attractions": curated_attractions,
            })
        parts.append(f"--- ATTRACTIONS ---\n{json.dumps(curated_segments, ensure_ascii=False, indent=2)}\n")

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
    """Synthesize Agent — Compiles curated agent data and aggregated costs into final response.
    
    Also updates current_plan with pipeline outputs and generates last_suggestions
    for the Intent Agent to use in the next turn.
    """
    logger.info("=" * 60)
    logger.info("📝 [SYNTHESIZE] Node entered")
    agent_outputs = state.get("agent_outputs", {})
    intent = state.get("routed_intent", "greeting")
    plan = state.get("macro_plan", {})
    current_plan = state.get("current_plan") or {}

    # Determine mode
    STANDALONE_INTENTS = ("search_flights", "search_hotels", "suggest_attractions", "search_restaurants", "preparation_inquiry")
    SELECT_INTENTS = ("select_flight", "select_hotel", "select_restaurant")
    is_standalone = intent in STANDALONE_INTENTS
    is_select = intent in SELECT_INTENTS
    is_simple = intent in ("greeting", "clarification_needed", "general_question")

    plan_context = current_plan.get("plan_context", {})
    mobility_plan = plan.get("mobility_plan", {})
    
    # We prioritize user_request_rewrite to focus Synthesize on the actionable intent
    last_intent_info = state.get("last_intent") or {}
    user_request_rewrite = last_intent_info.get("user_request_rewrite", "")
    
    # Determine what sections are already built to prompt next-step suggestions
    built_sections = []
    if current_plan.get("itinerary"): built_sections.append("Full Itinerary")
    if current_plan.get("budget"): built_sections.append("Budget")
    if current_plan.get("packing"): built_sections.append("Packing List")
    if plan_context: built_sections.append("Basic Trip Parameters")

    built_sections_text = ', '.join(built_sections) if built_sections else 'Nothing yet'
    system_content = SYNTHESIZE_SYSTEM.replace("{built_sections_text}", built_sections_text)
    aggregated_costs = {}

    if is_simple:
        system_content += "\n\nThis is a simple query/greeting. Respond naturally to the user in their language without outputting a full travel plan template."
        structured_output = {}
    elif is_standalone:
        # ═══ STANDALONE MODE ═══
        agent_name_map = {
            "search_flights": "Flight",
            "search_hotels": "Hotel",
            "suggest_attractions": "Attraction",
            "search_restaurants": "Restaurant",
            "preparation_inquiry": "Preparation & Budget",
        }
        agent_label = agent_name_map.get(intent, "Agent")
        response_language = plan_context.get("language", "en")

        system_content += f"""

## RESPONSE LANGUAGE
You MUST respond in language code: {response_language}
All your output text must be in this language.

## STANDALONE SEARCH RESULT
You are presenting {agent_label} search results — NOT a full travel plan.
- ONLY present data relevant to the user's specific request (see "User's Specific Request" below).
- FORMATTING: Present the results using clean, highly readable Markdown.
  - For Hotels, Flights, Attractions, and Restaurants: Do NOT generate Markdown tables or bullet point lists for the raw data items!
    Instead, simply introduce them with rich, natural sentences (like a travel guide), and then output EXACTLY the corresponding text placeholder on a new line:
    - `[HOTEL_UI_WIDGET]` (for search_hotels)
    - `[FLIGHT_UI_WIDGET]` (for search_flights)
    - `[ATTRACTION_UI_WIDGET]` (for suggest_attractions)
    - `[RESTAURANT_UI_WIDGET]` (for search_restaurants)
    Example for Hotels:
    "Here are some stunning hotels I found in the area:
    [HOTEL_UI_WIDGET]
    Let me know if you would like me to select one!"
    Example for Attractions:
    "Here are some highly recommended places to visit:
    [ATTRACTION_UI_WIDGET]
    (Include rich descriptions before or after the widget if helpful)"
- If NO results were found (empty data, errors), clearly explain to the user that no results matched their criteria and suggest adjustments (e.g. different dates, wider budget, different location).
- Make sure to clearly display ALL important information from the search data. Always include prices, timings, and links if available.
- Do NOT generate full travel plan sections (no itinerary, no flight info, no hotel info) unless that's what the user asked.
- Do NOT output sections for agents that did NOT run.
- At the end:
  1. Ask the user if they are satisfied with these results, or if they want to modify the search.
  2. IF the user already has a built itinerary (check Current Plan Status below), ask if they want to SELECT one of the options to update their itinerary. Do NOT ask them to select an option if they don't have an itinerary yet.
  3. Briefly suggest 1-2 next steps for other components of the trip that haven't been planned yet.
- Do NOT invent unrelated notes.
"""
        # Add user_request_rewrite for focus
        if user_request_rewrite:
            system_content += f"\n## User's Specific Request\n{user_request_rewrite}\nIMPORTANT: Focus your response ONLY on answering this specific request. Do not generate unrelated sections.\n"

        # Inject built sections context
        if built_sections:
            system_content += f"\n## Current Plan Status\nThe user already has these sections built: {', '.join(built_sections)}.\nUse this context to suggest appropriate next steps.\n"


        # Filter agent_outputs so LLM ONLY sees the data for THIS standalone agent
        agent_key_map_standalone = {
            "search_flights": "flight_agent",
            "search_hotels": "hotel_agent",
            "suggest_attractions": "attraction_agent",
            "search_restaurants": "restaurant_agent",
            "preparation_inquiry": "preparation_agent",
        }
        target_agent_key = agent_key_map_standalone.get(intent)
        filtered_outputs = {target_agent_key: agent_outputs.get(target_agent_key)} if target_agent_key and target_agent_key in agent_outputs else {}

        # Build curated context for standalone
        context_str = _build_curated_context(filtered_outputs, plan_context, {}, mobility_plan)
        if context_str:
            system_content += f"\n\n## Agent Data:\n{context_str}"
    else:
        # ═══ PIPELINE MODE ═══
        response_language = plan_context.get("language", "en")
        system_content += f"""

## RESPONSE LANGUAGE
You MUST respond in language code: {response_language}
All your output text must be in this language.
"""
        # Add draft mode note if applicable
        if intent == "draft_plan":
            system_content += """

## DRAFT MODE — STRICT RULES
This is a DRAFT plan. The following agents did NOT run: Flight, Hotel, Restaurant.
- DO NOT invent missing data. If constraints couldn't be met, honestly state it.
- Since this is an isolated query, mention what exists explicitly in the data block.
- At the end of your response, ask if they are satisfied with these results or if they want to modify them. Also briefly suggest continuing to build the rest of their plan (e.g. itinerary, budget) if they haven't been built yet.
- Budget estimates for flights/hotels/restaurants come from the Preparation Agent — show them ONLY in the 💰 Budget Breakdown table, clearly marked as estimates (~).
"""

        # 1. Aggregate Costs
        logger.info("   Aggregating costs...")
        aggregated_costs = aggregate_all_costs(agent_outputs, plan_context, mobility_plan)

        # 2. Build curated context — only fields Synthesize actually needs
        context_str = _build_curated_context(agent_outputs, plan_context, aggregated_costs, mobility_plan)
        system_content += f"\n\n## Agent Data for Synthesis:\n{context_str}"

        # 3. Add user_request_rewrite for targeted responses
        if user_request_rewrite:
            system_content += f"\n\n## User's Specific Request\n{user_request_rewrite}\n"


        # 4. Add itinerary modification mode instructions
        if intent == "modify_itinerary":
            itinerary_data = agent_outputs.get("itinerary_agent", {})
            mod_notes = itinerary_data.get("modification_notes", "")
            fulfilled = itinerary_data.get("fulfilled_user_request", True)

            modify_instructions = """

## ITINERARY MODIFICATION RESULT
You are presenting an UPDATED itinerary after the user requested changes.

**CRITICAL RULES:**
- Present the schedule EXACTLY as provided in the data. Do NOT re-arrange, re-time, or adjust any stops to try and "please" the user. The data you receive is the final validated result.
- Present the full updated Daily Itinerary
- Do NOT include sections for Flights, Accommodation, Budget, Packing List, or Travel Notes — they haven't changed
- Do NOT output any UI widget tags (`[FLIGHT_UI_WIDGET]`, `[HOTEL_UI_WIDGET]`, `[ATTRACTION_UI_WIDGET]`, `[RESTAURANT_UI_WIDGET]`). This is a modification action, not a search action.
- Keep the response focused on the itinerary changes
"""
            if not fulfilled and mod_notes:
                modify_instructions += f"""
## CONSTRAINT COMPROMISE (MUST EXPLAIN TO USER)
The Itinerary Agent could NOT fulfill the user's exact request due to real-world constraints.
You MUST apologize, explain exactly why their original request failed, and present the compromise schedule.

Notes from Itinerary Agent:
{mod_notes}

Example response tone: "I've updated the schedule, but unfortunately, I couldn't put [attraction] in the morning because it is closed at that time. I've scheduled it for [new time] instead. Is this alternative acceptable to you?"
Do NOT hide these adjustments. The user MUST understand why you didn't do exactly what they asked.
"""
            elif fulfilled:
                modify_instructions += """
## SUCCESSFUL MODIFICATION
The schedule was updated successfully without constraint conflicts.
At the end, suggest next steps in the user's language based on what they might want to do next (e.g., "Bạn muốn chỉnh sửa thêm gì nữa không? Hay chuyển sang tìm khách sạn?").
"""
            system_content += modify_instructions

        # 5. Add selection-triggered rerange instructions
        if is_select:
            selection_update = state.get("selection_update", {})
            sel_type = selection_update.get("type", "")
            
            selection_instructions = """

## SELECTION APPLIED
The user selected a new {sel_type} from previous search results.

**CRITICAL RULES:**
- Confirm the selection clearly and enthusiastically at the start of your response
- Do NOT present the full Daily Itinerary. The user already knows the schedule.
- Instead, briefly summarize what CHANGED as a result of this selection:
  - For flight: mention the new arrival/departure times and how Day 1 or the last day's schedule was adjusted
  - For hotel: mention the new hotel name and any check-in/check-out time changes
  - For restaurant: mention which meal was updated
- Do NOT include any other sections (Budget, Packing, Notes, Weather)
- Do NOT output any UI widget tags (`[FLIGHT_UI_WIDGET]`, `[HOTEL_UI_WIDGET]`, `[ATTRACTION_UI_WIDGET]`, `[RESTAURANT_UI_WIDGET]`). This is a selection action, not a search action.
- At the end, suggest 1-2 next steps
""".format(sel_type=sel_type)

            if sel_type == "hotel":
                hotel_name = selection_update.get("hotel_name", "")
                selection_instructions += f"\nUser selected hotel: **{hotel_name}**. Confirm the selection and note any schedule impacts.\n"
            elif sel_type == "flight":
                selection_instructions += "\nUser selected a new flight. Briefly note how Day 1 and/or the last day were adjusted.\n"
            elif sel_type == "restaurant":
                selection_instructions += "\nUser selected a new restaurant. Confirm which meal it replaces.\n"

            system_content += selection_instructions

        logger.info(f"   Curated context size: {len(context_str):,} chars")

    # ── (feasibility short circuit removed) ──

    # Build LLM messages — only system prompt + one user message
    llm_messages = [SystemMessage(content=system_content)]

    # Find the original user request: prioritize the rewritten, clear version from Intent Agent
    last_intent = state.get("last_intent", {})
    user_request = last_intent.get("user_request_rewrite")
    
    if not user_request:
        messages = state.get("messages", [])
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
        language = plan_context.get("language", "en")
        final_response = "Đã xảy ra lỗi khi tạo lịch trình của bạn. Vui lòng thử lại." if language == "vi" else "Sorry, an error occurred while generating your travel plan. Please try again."

    # Build structured output for frontend
    structured_output = {"intent": intent}

    if is_standalone:
        # Standalone: include ONLY the newly generated relevant agent output to prevent DB overwrites
        agent_key_map_standalone = {
            "search_flights": "flight_agent",
            "search_hotels": "hotel_agent",
            "suggest_attractions": "attraction_agent",
            "search_restaurants": "restaurant_agent",
            "preparation_inquiry": "preparation_agent",
        }
        target_agent_key = agent_key_map_standalone.get(intent)
        
        if target_agent_key == "flight_agent" and "flight_agent" in agent_outputs:
            structured_output["flights"] = agent_outputs["flight_agent"]
        elif target_agent_key == "hotel_agent" and "hotel_agent" in agent_outputs:
            structured_output["hotels"] = agent_outputs["hotel_agent"]
        elif target_agent_key == "attraction_agent" and "attraction_agent" in agent_outputs:
            structured_output["attractions"] = agent_outputs["attraction_agent"]
        elif target_agent_key == "restaurant_agent" and "restaurant_agent" in agent_outputs:
            structured_output["restaurants"] = agent_outputs["restaurant_agent"]
        elif target_agent_key == "preparation_agent" and "preparation_agent" in agent_outputs:
            structured_output["preparation"] = agent_outputs["preparation_agent"]
            # Build apply_data for preparation standalone
            try:
                apply_data = build_sectioned_apply_data(
                    agent_outputs, plan_context, None,
                    changed_sections={"budget", "packing", "notes"},
                )
                structured_output["apply_data"] = apply_data
            except Exception as e:
                logger.error(f"Failed to build apply_data for preparation: {e}")

        if plan_context:
            structured_output["plan_context"] = plan_context

    elif not is_simple:
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
            if intent in ["modify_itinerary", "select_restaurant"]:
                # Sectioned format: only apply itinerary section
                apply_data = build_sectioned_apply_data(
                    agent_outputs, plan_context, aggregated_costs,
                    changed_sections={"itinerary"},
                )
            elif intent in ["select_hotel", "select_flight"]:
                # Select flow: only itinerary changed, budget managed by user
                apply_data = build_sectioned_apply_data(
                    agent_outputs, plan_context, aggregated_costs,
                    changed_sections={"itinerary"},
                )
            else:
                # Full format: apply all sections
                apply_data = build_sectioned_apply_data(
                    agent_outputs, plan_context, aggregated_costs,
                    changed_sections=None,  # all sections
                )
            structured_output["apply_data"] = apply_data
        except Exception as e:
            logger.error(f"   ❌ Failed to build apply_data: {e}", exc_info=True)
            structured_output["apply_data"] = None

    # ── Update current_plan ────────────────────────────────────────
    if is_standalone:
        # Standalone: update only the relevant section
        if plan_context:
            current_plan["plan_context"] = plan_context
        if "flight_agent" in agent_outputs:
            current_plan["flight_search"] = agent_outputs["flight_agent"]
        if "hotel_agent" in agent_outputs:
            current_plan["hotel_search"] = agent_outputs["hotel_agent"]
        if "attraction_agent" in agent_outputs:
            current_plan["attraction_search"] = agent_outputs["attraction_agent"]
        if "restaurant_agent" in agent_outputs:
            current_plan["restaurant_search"] = agent_outputs["restaurant_agent"]
        if "preparation_agent" in agent_outputs:
            prep = agent_outputs["preparation_agent"]
            current_plan["budget"] = prep.get("budget", {})
            current_plan["packing"] = prep.get("packing_lists", [])
            current_plan["notes"] = prep.get("notes", [])

    elif not is_simple:
        current_plan["plan_context"] = plan_context
        if intent != "modify_itinerary" and not is_select:
            current_plan["is_draft"] = (intent == "draft_plan")

        if "itinerary_agent" in agent_outputs:
            current_plan["itinerary"] = agent_outputs["itinerary_agent"]
        if "preparation_agent" in agent_outputs:
            prep = agent_outputs["preparation_agent"]
            current_plan["budget"] = prep.get("budget", {})
            current_plan["packing"] = prep.get("packing_lists", [])
            current_plan["notes"] = prep.get("notes", [])
        # Persist search results for future select_* intents
        if "flight_agent" in agent_outputs:
            current_plan["flight_search"] = agent_outputs["flight_agent"]
        if "hotel_agent" in agent_outputs:
            current_plan["hotel_search"] = agent_outputs["hotel_agent"]
        if "restaurant_agent" in agent_outputs:
            current_plan["restaurant_search"] = agent_outputs["restaurant_agent"]
        if "attraction_agent" in agent_outputs:
            current_plan["attraction_search"] = agent_outputs["attraction_agent"]
        if aggregated_costs:
            current_plan["aggregated_costs"] = aggregated_costs

    # ── Generate last_suggestions ──────────────────────────────────
    last_suggestions = _generate_suggestions(intent, agent_outputs, current_plan)
    current_plan["last_suggestions"] = last_suggestions
    logger.info(f"   💡 Suggestions: {[s['label'] for s in last_suggestions]}")

    logger.info("📝 [SYNTHESIZE] Node completed")
    logger.info("=" * 60)
    return {
        "final_response": final_response,
        "structured_output": structured_output,
        "current_plan": current_plan,
        "messages": [AIMessage(content=final_response)],
    }


def _generate_suggestions(intent: str, agent_outputs: dict, current_plan: dict) -> list[dict]:
    """Generate contextual next-step suggestions based on current intent and global state."""
    
    is_draft = current_plan.get("is_draft", True)
    has_flights = "flight_search" in current_plan or current_plan.get("mobility_plan", {}).get("inbound_flight")
    has_hotels = "hotel_search" in current_plan or "mobility_plan" in current_plan
    
    SELECT_INTENTS = ("select_flight", "select_hotel")
    is_select = intent in SELECT_INTENTS
    
    suggestions = []
    
    if intent == "draft_plan":
        suggestions = [
            {"label": "Search flights", "action": "search_flights"},
            {"label": "Search hotels", "action": "search_hotels"},
            {"label": "Search restaurants", "action": "search_restaurants"},
        ]
    elif intent == "modify_itinerary" or is_select:
        suggestions.append({"label": "Modify more", "action": "modify_plan"})
        if not has_flights:
            suggestions.append({"label": "Search flights", "action": "search_flights"})
        if not has_hotels:
            suggestions.append({"label": "Search hotels", "action": "search_hotels"})
        if has_flights and has_hotels:
            suggestions.append({"label": "Search restaurants", "action": "search_restaurants"})
    elif intent == "full_plan":
        suggestions = [
            {"label": "Modify itinerary", "action": "modify_plan"},
            {"label": "Change hotel", "action": "search_hotels"},
            {"label": "Find restaurants", "action": "search_restaurants"},
        ]
    elif intent == "preparation_inquiry":
        suggestions = [
            {"label": "Create detailed plan", "action": "draft_plan"},
        ]
    elif intent == "search_flights":
        if not has_hotels:
            suggestions.append({"label": "Search hotels", "action": "search_hotels"})
        suggestions.append({"label": "Modify itinerary", "action": "modify_plan"})
    elif intent == "search_hotels":
        if not has_flights:
            suggestions.append({"label": "Search flights", "action": "search_flights"})
        suggestions.append({"label": "Search restaurants", "action": "search_restaurants"})
    elif intent == "suggest_attractions":
        suggestions = [
            {"label": "Create plan", "action": "draft_plan"},
            {"label": "Search restaurants", "action": "search_restaurants"},
        ]
    elif intent == "search_restaurants":
        if not has_flights:
            suggestions.append({"label": "Search flights", "action": "search_flights"})
        if not has_hotels:
            suggestions.append({"label": "Search hotels", "action": "search_hotels"})
        suggestions.append({"label": "Modify itinerary", "action": "modify_plan"})
        
    # Ensure max 3 suggestions
    return suggestions[:3]
