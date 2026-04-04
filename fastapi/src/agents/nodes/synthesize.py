import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from src.agents.state import GraphState
from src.agents.nodes.utils import llm_streaming
from src.services.cost_aggregator import aggregate_all_costs
from src.services.apply_data_builder import build_apply_data
from src.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
logger = logging.getLogger(__name__)

llm_synthesize = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=True,
)

SYNTHESIZE_SYSTEM = """You are the Synthesize Agent for a travel planning system.
Compile ALL agent data into a clear, engaging response for the user.
Your job is to compile ALL the provided specialist agent data (itinerary, budget, flights, hotels, restaurants, etc.) into a cohesive, engaging, and comprehensive travel plan for the user.
## Response Format
Use markdown with these sections (skip those with no data):
## Persona & Tone
- Act as an intelligent, conversational AI travel assistant.
- Use a natural, friendly tone. Avoid overly formal or robotic "travel agency" phrasing (e.g., do NOT say "Chào mừng quý khách", "I have compiled data from experts", or "Dear customer").
- Start directly with a warm, concise opening that addresses the user's specific request.
- Do not hallucinate or assume details (e.g., do not mention a "family" if the user didn't specify who they are traveling with).
- Write the entire response in the language specified in the "User Language" section. THIS IS CRITICAL.
### 🗺️ Trip Overview
Brief summary: destination, dates, travelers, trip style.
## Formatting Instructions
- Be organized and professional.
- **MAXIMIZE MARKDOWN FORMATTING**: Use headings (`#`, `##`, `###`) for scale, **bold** for important names/prices/times, *italics* for notes, blockquotes (`>`) for highlights or tips, and lots of relevant emojis 🌴✈️🍲 to make it vibrant and easy to read.
- Do NOT output raw JSON dumps. Incorporate the data naturally into your text.
### 📅 Daily Itinerary
Day-by-day schedule with times, places, and activities.
## Required Sections (if data is provided):
1. **Trip Overview**: Destination, dates, travelers, and a brief summary of the trip style.
2. **Flights ✈️**: Recommended flights (outbound/return) with times, flight numbers, and total prices.
3. **Accommodation 🏨**: Where they are staying, check-in/out dates, and why it was chosen.
4. **Daily Itinerary 📅**: A detailed day-by-day, step-by-step breakdown.
   - Mention times, places, and activities.
   - For meals, clearly suggest the recommended restaurants and estimated costs.
   - For attractions, mention any "includes" (sub-attractions) they will visit.
5. **Budget Breakdown 💰**: Use the Aggregated Budget data to summarize expected expenses by category (Flights, Accommodation, Attractions, Restaurants, Other) and provide the Grand Total in the requested currency.
6. **Packing List & Weather 🎒**: What to bring based on the forecasts.
7. **Travel Notes 📝**: Important tips, safety info, and reminders.
### 🏨 Accommodation
Hotel recommendations with prices and highlights.
### ✈️ Flights
Flight options with prices, times, airlines.
### 💰 Budget Estimate
Budget breakdown by category.
### 🎒 Packing List
What to bring based on weather and activities.
### 📝 Travel Notes
Important tips, safety info, local customs.
## Rules
- Write in English by default
- Use emoji for section headers
- Include specific times, prices, and ratings
- For simple queries (greetings), respond naturally without template
- Highlight top recommendations
Be detailed! Don't just list places; use the notes/descriptions from the agents to explain *why* something is recommended or what they will do there.
"""
async def synthesize_agent_node(state: GraphState) -> dict[str, Any]:
    """Synthesize Agent — Compiles all agent data into final response."""
    """Synthesize Agent — Compiles all agent data and aggregated costs into final response."""
    logger.info("=" * 60)
    logger.info("📝 [SYNTHESIZE] Node entered")
    agent_outputs = state.get("agent_outputs", {})
    conversation_messages = state.get("messages", [])
    plan = state.get("orchestrator_plan", {})
    intent = plan.get("intent", "greeting")
    plan_context = plan.get("plan_context", {})
    language = plan_context.get("language", "en")
    # Build context from agent outputs
    context_parts = []
    for agent_name, data in agent_outputs.items():
        if agent_name == "orchestrator":
            continue
        if data and not isinstance(data, str):
            context_parts.append(f"\n--- {agent_name.upper()} ---")
            context_parts.append(json.dumps(data, indent=2, default=str, ensure_ascii=False)[:2000])
    is_simple = intent in ("greeting", "information_query", "clarification_needed") or not plan_context
    context_str = "\n".join(context_parts) if context_parts else "No specialist data."
    is_simple = intent in ("greeting", "information_query", "clarification_needed") or not context_parts
    system_content = SYNTHESIZE_SYSTEM
    aggregated_costs = {}
    
    if is_simple:
        system_content += "\n\nSimple query. Respond naturally."
        system_content += "\n\nThis is a simple query/greeting. Respond naturally to the user in their language without outputting a full travel plan template."
        structured_output = {}
    else:
        system_content += f"\n\nAgent Data:\n{context_str}"
        # 1. Aggregate Costs
        logger.info("   Aggregating costs...")
        aggregated_costs = aggregate_all_costs(agent_outputs, plan_context)
        
        # 2. Build Context String
        context_parts = [
            f"--- USER LANGUAGE ---\nLanguage Code: {language}\n",
            f"--- PLAN CONTEXT ---\n{json.dumps(plan_context, ensure_ascii=False, indent=2)}\n",
            f"--- AGGREGATED BUDGET ---\n{json.dumps(aggregated_costs, ensure_ascii=False, indent=2)}\n"
        ]
        
        for key in ["flight_agent", "hotel_agent", "attraction_agent", "itinerary_agent", "restaurant_agent", "preparation_agent"]:
            if key in agent_outputs and not agent_outputs[key].get("skipped", False):
                # Trim very large data if necessary, but keep it mostly intact for synthesis
                data_str = json.dumps(agent_outputs[key], ensure_ascii=False, indent=2)
                if len(data_str) > 8000:
                    data_str = data_str[:8000] + "\n...[TRUNCATED]"
                context_parts.append(f"--- {key.upper()} ---\n{data_str}")
                
        context_str = "\n".join(context_parts)
        system_content += f"\n\n## Agent Data for Synthesis:\n{context_str}"
    llm_messages = [SystemMessage(content=system_content)]
    
    # Add recent conversation history so LLM knows what user asked
    for msg in conversation_messages[-10:]:
        content = msg.content if hasattr(msg, "content") else str(msg)
        if content.startswith("["):
            continue
        if isinstance(msg, HumanMessage):
            llm_messages.append(msg)
        elif isinstance(msg, AIMessage):
            llm_messages.append(msg)
    if not any(isinstance(m, HumanMessage) for m in llm_messages):
        llm_messages.append(HumanMessage(content="Hello"))
        llm_messages.append(HumanMessage(content="Please provide my travel plan."))
    try:
        logger.info("   Invoking LLM for synthesis...")
        result = await llm_synthesize.ainvoke(llm_messages)
        
        raw_resp = result.content
        if isinstance(raw_resp, list):
            # Extract text from list of dicts/strings
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
        if "attraction_agent" in agent_outputs:
            structured_output["attractions"] = agent_outputs["attraction_agent"].get("attractions", [])
        if "restaurant_agent" in agent_outputs:
            structured_output["restaurants"] = agent_outputs["restaurant_agent"].get("restaurants", [])
        if "hotel_agent" in agent_outputs:
            structured_output["hotels"] = agent_outputs["hotel_agent"].get("recommendations", [])
        structured_output["plan_context"] = plan_context
        structured_output["aggregated_costs"] = aggregated_costs
        
        # Pass through relevant sections if UI needs them
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
        if "itinerary_agent" in agent_outputs:
            structured_output["daily_schedules"] = agent_outputs["itinerary_agent"].get("daily_schedules", [])
        if "preparation_agent" in agent_outputs:
            structured_output["preparation"] = agent_outputs["preparation_agent"]

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