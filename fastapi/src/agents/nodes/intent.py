"""
Intent Agent — Routing + Context Tracking.

Lightweight LLM node that:
1. Reads current_plan (including last_suggestions) + latest user message
2. Detects intent and context changes (date, destination, etc.)
3. Updates current_plan with context changes
4. Routes to appropriate agent/pipeline

Uses flash-lite for speed (~1-2s).
"""
import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.agents.state import GraphState
from src.agents.nodes.utils import _extract_json, _run_agent_with_tools
from src.config import settings

logger = logging.getLogger(__name__)


llm_intent = (
    ChatOpenAI(
        model=settings.MODEL_NAME,
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.1,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model=settings.MODEL_NAME,
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_INTENT or settings.GOOGLE_GEMINI_API_KEY,
        temperature=0.1,
        streaming=False,
    )
)

# ── System prompt ──────────────────────────────────────────────────────
INTENT_SYSTEM = """\
You are the Intent Router for a multi-agent travel planning chatbot.

Your job:
1. Determine the user's intent from their message
2. Detect any changes to trip context (dates, destination, etc.)
3. Return structured JSON

## Available Intents

### Direct response (no agent needed)
- `general` — User says hi, thanks, bye, or asks a general question not related to building/modifying a plan (e.g. "What's the weather like in December?", "Do I need a visa?")
- `clarification_needed` — User's message is ambiguous or missing critical info

### Planning (needs Macro Planning → full pipeline)
- `draft_plan` — User wants a NEW travel plan (or destination changed → rebuild from scratch)
- `full_plan` — User explicitly wants full details with real flights/hotels/restaurants

### Selective agent (single agent — handles BOTH new and correction/modification)
- `search_flights` — User wants to find flights OR correct/adjust flight results
- `search_hotels` — User wants to find hotels OR correct/adjust hotel results
- `suggest_attractions` — User wants attraction suggestions OR adjust attraction list
- `search_restaurants` — User wants restaurant recommendations OR adjust restaurant choices
- `preparation_inquiry` — User asks about budget, costs, packing, travel tips, or notes for the FIRST TIME or wants a complete refresh

### Selection (user picks from previous search results)
- `select_flight` — User selects/chooses a specific flight from previous search_flights results. REQUIRES: "flight_search" in Available search results. Examples: "Lấy chuyến VN240", "Chọn chuyến bay đầu tiên", "I'll take the Vietnam Airlines flight"
- `select_hotel` — User selects/chooses a specific hotel from previous search_hotels results. REQUIRES: "hotel_search" in Available search results. Examples: "Chọn khách sạn Oriental Jade", "I want the first hotel", "Lấy khách sạn thứ 2"
- `select_restaurant` — User selects/chooses a specific restaurant from previous search_restaurants results to add to their itinerary. REQUIRES: "restaurant_search" in Available search results. Examples: "Thêm quán phở thìn vào lịch trình", "Chọn quán đầu tiên cho bữa trưa"

### Modification (requires existing data in current_plan)
- `modify_itinerary` — User wants to modify the EXISTING itinerary schedule: swap/add/remove specific attractions, change visit times or order, rearrange daily schedule, reduce visit duration, replace attractions with new ones, etc. REQUIRES: current_plan must have an itinerary section (Built sections includes "itinerary"). The Itinerary Agent will handle everything including suggesting new attractions if needed.
- `modify_preparation` — User wants to modify/correct EXISTING budget, packing list, or travel notes. REQUIRES: current_plan has budget/packing/notes sections (Built sections includes "budget", "packing", or "notes"). Examples: "Sửa tiền khách sạn thành 2 triệu", "Thêm mục dự phòng 500k", "Bỏ mục shopping"


## IMPORTANT — Correction vs Structural Change vs Itinerary Modification

When user comments on or corrects a previous chatbot response about a SPECIFIC topic:
- Budget/cost correction (e.g., "3 nights not 4", "too expensive, reduce it") → `modify_preparation` (if budget/packing/notes already in Built sections)
- Flight preference (e.g., "find an earlier morning flight") → `search_flights`
- Hotel adjustment (e.g., "I want a cheaper hotel") → `search_hotels`
- Attraction suggestion (e.g., "suggest more fun places") → `suggest_attractions` (standalone search, NOT modifying itinerary)

When user wants to change the EXISTING ITINERARY (requires "itinerary" in Built sections):
- Remove attraction (e.g., "remove the Mausoleum from the schedule") → `modify_itinerary`
- Rearrange (e.g., "move Temple of Literature to morning of day 3") → `modify_itinerary`
- Swap/replace with new (e.g., "replace the Mausoleum with something else") → `modify_itinerary`
- Add new place (e.g., "add a place in the afternoon of day 2") → `modify_itinerary`
- Adjust timing (e.g., "reduce time at Temple of Literature") → `modify_itinerary`
- Change daily start time (e.g., "start each day at 8am", "I want to start earlier") → `modify_itinerary`
- Change pace/rhythm (e.g., "make it more relaxed", "pack in more activities") → `modify_itinerary`


## Selection vs Search
- If user says "chọn/lấy/dùng hotel X" or "I'll take flight Y" AND the plan already has search results ("flight_search", "hotel_search", or "restaurant_search" in Available search results) → use `select_flight` / `select_hotel` / `select_restaurant`
- If NO search results exist and user mentions a preference → route to `search_hotels` / `search_flights` / `search_restaurants` to search first
- If user says "tìm quán khác", "khách sạn khác" when search results exist → search mode (new search, not selection)

## Rules

1. Check `last_suggestions` — if user says "okay", "yes", "sure", "do it", map to the suggested action.
   If multiple suggestions exist and user's response is ambiguous, set intent to `clarification_needed`.

2. Check `current_plan` — if user already has a plan and asks to "plan a trip" again for the SAME destination,
   this is likely a modification of what they already have. Route to the appropriate agent.

3. For `draft_plan`: user describes a trip WITHOUT specifying flight/hotel details.
   Example: "I want to go to Da Nang for 3 days", "Plan a trip to Tokyo"

4. For `full_plan`: user explicitly asks for real flights/hotels.
   Example: "Create a full plan with real flights and hotels"

5. Detect context_updates when user mentions/changes trip parameters.
   You MUST use these EXACT field names (matching the plan_context schema):
   - `departure` — origin city (e.g. "Ho Chi Minh City"). NOT "origin".
   - `destination` — destination city  
   - `start_date` — trip start (ISO format: "2026-05-20")
   - `end_date` — trip end (ISO format)
   - `num_days` — number of days. NOT "duration_days" or "duration".
   - `adults` — number of adults (integer). Default to 1 if the user does not specify passenger counts.
   - `children` — number of children (integer)
   - `children_ages` — ages of children (e.g. "5,8")
   - `infants` — number of infants (integer)
   - `interest` — interests/preferences (e.g. "history, food, culture")
   - `pace` — "relaxed" | "moderate" | "packed"
   - `budget_level` — "budget" | "moderate" | "luxury"
   - `currency` — e.g. "VND", "USD"
   - `language` — language code (e.g. "vi", "en", "ja")
   - `local_transportation` — "car" | "walking" | "motorbike" | "taxi"
   Only include fields that ACTUALLY appear in the user's message, EXCEPT:
   - `adults`: Set to 1 if no passengers are mentioned and the plan doesn't already have an adults count.
   - `language`: Detect from the language the user writes in (Vietnamese → "vi", English → "en", etc.)
   - `currency`: Infer from destination country or user's language (Vietnamese → "VND", English → "USD", etc.)
   Always include `language` and `currency` in context_updates on EVERY request (even if already set),
   because the user may switch languages mid-conversation.

6. **MISSING INFORMATION RULE FOR CHILDREN THAT MUST BE ASKED**:
   ONLY apply this rule if the intent is `full_plan`, `search_flights`, or `search_hotels`. Do NOT ask for children's ages for `draft_plan` or other intents.
   If the intent IS one of those three AND there are children traveling (`children` > 0 in either plan_context or the user's message), but `children_ages` is NOT provided (neither in plan_context nor the user's message):
   - You MUST change the intent to `clarification_needed`.
   - Ask the user for the children's ages in the `direct_response` (in their language).
   - Example: "Please provide the ages of the children so I can find accurate flights and hotels."

7. For `general` and `clarification_needed`: provide `direct_response`.
   IMPORTANT: `direct_response` MUST be written in the SAME language the user used.

7. If user requests MULTIPLE searches (e.g. "find flights and hotels"), pick the FIRST/primary one as intent.
   The system will suggest the remaining searches as next steps automatically.

8. **Follow-up / Correction detection**: Check `Built sections` in the current plan context.
   If the plan already has a section (budget, itinerary, etc.) and the user comments on or corrects it:
   - Route to the CORRECT specific agent intent based on WHAT they're talking about
   - Do NOT blindly repeat `last_intent` — determine the topic from the user's message

## Response Format

CRITICAL: Your response must be one valid JSON object. No text before or after.

```json
{
    "intent": "draft_plan",
    "context_updates": {},
    "direct_response": null,
    "user_request_rewrite": null
}
```

- `intent`: one of the intent strings above
- `context_updates`: dict of changed fields (empty {} if no changes). MUST ALWAYS include `language` and `currency`.
- `direct_response`: text response for greeting/clarification/general (null otherwise). MUST be in the user's language.
- `constraint_overrides`: ONLY for confirmed/existing flight or hotel times. null in most cases. Use this ONLY when the user states they ALREADY HAVE a specific flight or hotel booking with fixed times (e.g., "I already booked a flight departing at 8:00 AM", "my flight arrives at 10:00"). Do NOT use this for search preferences (e.g., "find me a flight around 8-10 AM" — that goes into user_request_rewrite instead).
  Possible keys (only when user ALREADY HAS confirmed times):
  - `outbound_departure_time` — "HH:MM" confirmed outbound flight departure
  - `outbound_arrival_time` — "HH:MM" confirmed outbound flight arrival
  - `return_departure_time` — "HH:MM" confirmed return flight departure
  - `return_arrival_time` — "HH:MM" confirmed return flight arrival
  - `hotels` — list of per-segment hotel overrides: `[{"nights": [1,2,3], "check_in_time": "HH:MM", "check_out_time": "HH:MM"}]`
  Examples:
  - "I have a flight at 8 AM" → constraint_overrides: {"outbound_departure_time": "08:00"}
  - "Find flights around 8-10 AM" → constraint_overrides: null (put time preference in user_request_rewrite)
  - "I want to depart in the afternoon" → constraint_overrides: null (put in user_request_rewrite)
- `user_request_rewrite`: Required for ALL planning and modification intents (`draft_plan`, `full_plan`, `modify_itinerary`, `modify_preparation` AND all standalone agents like `search_flights`, `search_hotels`). null otherwise.
  A focused, 1-2 sentence description of what the user wants RIGHT NOW — their current request analyzed, disambiguated, and rewritten from their perspective. Include any new context or specific constraints they just mentioned (e.g. area, budget, style) so downstream agents know EXACTLY what goal to accomplish.
  Write in the SAME language as the user.
"""


def _summarize_plan(current_plan: dict) -> str:
    """Create a concise summary of current_plan for the Intent Agent."""
    if not current_plan:
        return "No plan yet."

    plan_ctx = current_plan.get("plan_context", {})
    parts = []

    # Trip basics
    dep = plan_ctx.get("departure", "")
    dest = plan_ctx.get("destination", "")
    start = plan_ctx.get("start_date", "")
    end = plan_ctx.get("end_date", "")
    num_days = plan_ctx.get("num_days", "")
    adults = plan_ctx.get("adults", 1)
    children = plan_ctx.get("children", 0)

    if dest:
        trip_info = f"Trip: {dep} → {dest}"
        if start and end:
            trip_info += f", {start} to {end}"
        if num_days:
            trip_info += f", {num_days} days"
        trip_info += f", {adults} adults"
        if children:
            trip_info += f" + {children} children"
        parts.append(trip_info)


    # What sections exist
    sections = []
    if current_plan.get("itinerary"):
        sections.append("itinerary")
    if current_plan.get("budget"):
        sections.append("budget")
    if current_plan.get("packing"):
        sections.append("packing")
    if current_plan.get("notes"):
        sections.append("notes")
    if sections:
        parts.append(f"Built sections: {', '.join(sections)}")

    # Available search results (for selection intents)
    search_results = []
    if current_plan.get("flight_search"):
        search_results.append("flight_search")
    if current_plan.get("hotel_search"):
        search_results.append("hotel_search")
    if current_plan.get("restaurant_search"):
        search_results.append("restaurant_search")
    if search_results:
        parts.append(f"Available search results: {', '.join(search_results)}")

    return " | ".join(parts) if parts else "No plan yet."


async def intent_agent_node(state: GraphState) -> dict[str, Any]:
    """Intent Agent — Routing + Context Tracking.

    Reads current_plan + last_suggestions + latest user message.
    Returns intent + context_updates + optionally direct_response.
    """
    logger.info("=" * 60)
    logger.info("🎯 [INTENT] Node entered")


    current_plan = state.get("current_plan") or {}

    # Get latest user message
    user_message = state.get("user_message", "")
    logger.info(f"   User message: {user_message[:100]}")

    # Build context for LLM
    plan_summary = _summarize_plan(current_plan)
    last_suggestions = current_plan.get("last_suggestions", [])
    last_intent = current_plan.get("last_intent", "")
    last_user_request = current_plan.get("last_user_request", "")
    plan_ctx_clean = current_plan.get("plan_context", {})

    from datetime import datetime
    current_date_str = datetime.now().strftime("%Y-%m-%d %A")

    context_msg = f"Current System Date: {current_date_str}\n"
    context_msg += f"Current plan: {plan_summary}"
    if last_intent:
        context_msg += f"\nLast intent (previous turn): {last_intent}"
    if last_user_request:
        context_msg += f"\nLast user request (previous turn): {last_user_request}"
    if last_suggestions:
        context_msg += f"\nLast suggestions: {json.dumps(last_suggestions, ensure_ascii=False)}"
    context_msg += f"\nCurrent Plan Context:\n{json.dumps(plan_ctx_clean, ensure_ascii=False, indent=2)}\n"

    logger.info(f"   System Date: {current_date_str}")
    logger.info(f"   Plan summary: {plan_summary}")
    logger.info(f"   Last intent: {last_intent}")
    logger.info(f"   Last suggestions: {last_suggestions}")

    try:
        result = await llm_intent.ainvoke([
            SystemMessage(content=INTENT_SYSTEM),
            SystemMessage(content=context_msg),
            HumanMessage(content=user_message),
        ])

        output = _extract_json(result.content)
        intent = output.get("intent", "general")
        context_updates = output.get("context_updates", {})
        direct_response = output.get("direct_response")
        constraint_overrides = output.get("constraint_overrides") or {}
        user_request_rewrite = output.get("user_request_rewrite")

        logger.info(f"   🎯 Intent: {intent}")
        if context_updates:
            logger.info(f"   📝 Context updates: {context_updates}")

        # Save context for next turn
        current_plan["last_intent"] = intent
        if user_request_rewrite:
            current_plan["last_user_request"] = user_request_rewrite

        # Apply context updates to current_plan
        if context_updates:
            plan_context = current_plan.get("plan_context", {})
            plan_context.update(context_updates)
            current_plan["plan_context"] = plan_context

        # Auto-compute end_date from start_date + num_days if missing
        plan_context = current_plan.get("plan_context", {})
        start_date = plan_context.get("start_date", "")
        num_days = plan_context.get("num_days")
        end_date = plan_context.get("end_date", "")
        if start_date and num_days and not end_date:
            try:
                from datetime import datetime, timedelta
                sd = datetime.strptime(start_date, "%Y-%m-%d")
                ed = sd + timedelta(days=int(num_days) - 1)
                plan_context["end_date"] = ed.strftime("%Y-%m-%d")
                current_plan["plan_context"] = plan_context
                logger.info(f"   📅 Auto-computed end_date: {plan_context['end_date']}")
            except Exception as e:
                logger.warning(f"   ⚠️ Failed to auto-compute end_date: {e}")

        # Direct response intents — return immediately
        if intent in ("general", "clarification_needed") and direct_response:
            logger.info(f"   💬 Direct response: {direct_response[:80]}...")
            return {
                "current_plan": current_plan,
                "intent_output": output,
                "final_response": direct_response,
                "agent_outputs": {"intent": {"intent": intent, "response": direct_response}},
            }

        # Routing intents — pass to next node
        STANDALONE_INTENTS = ("search_flights", "search_hotels", "suggest_attractions", "search_restaurants")

        state_update = {
            "current_plan": current_plan,
            "intent_output": output,
            "agent_outputs": {"intent": {"intent": intent, "context_updates": context_updates}},
        }

        # For standalone search intents: set macro_plan with user_request_rewrite
        # Search agents (flight, hotel, attraction, restaurant) read from macro_plan["agent_requests"]
        if intent in STANDALONE_INTENTS and user_request_rewrite:
            agent_key_map = {
                "search_flights": "flight",
                "search_hotels": "hotel",
                "suggest_attractions": "attraction",
                "search_restaurants": "restaurant",
            }
            agent_key = agent_key_map.get(intent, "")
            state_update["macro_plan"] = {
                "agent_requests": {agent_key: user_request_rewrite},
            }
            logger.info(f"   📋 User request rewrite [{agent_key}]: {user_request_rewrite[:100]}")



        if constraint_overrides:
            state_update["constraint_overrides"] = constraint_overrides
            logger.info(f"   🔧 Constraint overrides: {constraint_overrides}")
        return state_update

    except Exception as e:
        logger.error(f"   ❌ Intent Agent error: {e}", exc_info=True)

        # Try to extract a status code from the exception
        error_code = getattr(e, "status_code", getattr(e, "code", "Unknown"))
        plan_context = current_plan.get("plan_context", {})
        language = plan_context.get("language", "en")
        fallback = f"Đã xảy ra lỗi hệ thống (Mã lỗi: {error_code}). Vui lòng thử lại sau." if language == "vi" else f"I encountered an error (Code: {error_code}). Please try again later."

        return {
            "current_plan": current_plan,
            "intent_output": {"intent": "general"},
            "final_response": fallback,
            "agent_outputs": {"intent": {"error": str(e), "code": error_code}},
        }
