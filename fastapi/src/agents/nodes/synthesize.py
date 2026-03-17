import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
from src.agents.nodes.utils import llm_streaming


logger = logging.getLogger(__name__)

SYNTHESIZE_SYSTEM = """You are the Synthesize Agent for a travel planning system.

Compile ALL agent data into a clear, engaging response for the user.

## Response Format
Use markdown with these sections (skip those with no data):

### 🗺️ Trip Overview
Brief summary: destination, dates, travelers, trip style.

### 📅 Daily Itinerary
Day-by-day schedule with times, places, and activities.

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
"""


async def synthesize_agent_node(state: GraphState) -> dict[str, Any]:
    """Synthesize Agent — Compiles all agent data into final response."""
    logger.info("=" * 60)
    logger.info("📝 [SYNTHESIZE] Node entered")

    agent_outputs = state.get("agent_outputs", {})
    conversation_messages = state.get("messages", [])
    plan = state.get("orchestrator_plan", {})
    intent = plan.get("intent", "greeting")

    # Build context from agent outputs
    context_parts = []
    for agent_name, data in agent_outputs.items():
        if agent_name == "orchestrator":
            continue
        if data and not isinstance(data, str):
            context_parts.append(f"\n--- {agent_name.upper()} ---")
            context_parts.append(json.dumps(data, indent=2, default=str, ensure_ascii=False)[:2000])

    context_str = "\n".join(context_parts) if context_parts else "No specialist data."
    is_simple = intent in ("greeting", "information_query", "clarification_needed") or not context_parts

    system_content = SYNTHESIZE_SYSTEM
    if is_simple:
        system_content += "\n\nSimple query. Respond naturally."
    else:
        system_content += f"\n\nAgent Data:\n{context_str}"

    llm_messages = [SystemMessage(content=system_content)]
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

    try:
        result = await llm_streaming.ainvoke(llm_messages)
        final_response = result.content
    except Exception as e:
        logger.error(f"   ❌ Synthesize error: {e}")
        final_response = "Sorry, an error occurred. Please try again."

    # Build structured output for frontend
    structured_output = {}
    db_commands = []

    if not is_simple:
        structured_output = {"intent": intent}
        if "attraction_agent" in agent_outputs:
            structured_output["attractions"] = agent_outputs["attraction_agent"].get("attractions", [])
        if "restaurant_agent" in agent_outputs:
            structured_output["restaurants"] = agent_outputs["restaurant_agent"].get("restaurants", [])
        if "hotel_agent" in agent_outputs:
            structured_output["hotels"] = agent_outputs["hotel_agent"].get("recommendations", [])
        if "flight_agent" in agent_outputs:
            structured_output["flights"] = agent_outputs["flight_agent"].get("recommendations", [])
        if "preparation_agent" in agent_outputs:
            prep = agent_outputs["preparation_agent"]
            structured_output["budget"] = prep.get("budget", {})
            structured_output["packing_lists"] = prep.get("packing_lists", [])
            structured_output["notes"] = prep.get("notes", [])
        if "itinerary_agent" in agent_outputs:
            structured_output["daily_schedules"] = agent_outputs["itinerary_agent"].get("daily_schedules", [])

    logger.info("📝 [SYNTHESIZE] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "synthesize",
        "current_tool": "",
        "final_response": final_response,
        "structured_output": structured_output,
        "db_commands": db_commands,
        "messages": [AIMessage(content=final_response)],
    }
