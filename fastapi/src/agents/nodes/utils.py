"""
Common utilities and LLM instances for the LangGraph multi-agent travel planner.
"""

import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.state import GraphState
from src.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# LLM Instances
# ============================================================

llm_fast = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.3,
    streaming=False,
)

llm_streaming = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.7,
    streaming=True,
)

llm_agent = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)


# ============================================================
# Helper Functions
# ============================================================

def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response text, handling markdown code blocks."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return json.loads(text[start:end].strip())

    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return json.loads(text[start:end].strip())

    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])

    raise ValueError(f"No valid JSON found in LLM response: {text[:200]}...")


def _get_latest_user_message(state: GraphState) -> str:
    """Extract the most recent user message from state."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def _get_conversation_context(state: GraphState, max_messages: int = 10) -> list:
    """Build conversation context from message history."""
    messages = state.get("messages", [])
    context = []
    for msg in messages[-max_messages:]:
        content = msg.content if hasattr(msg, "content") else str(msg)
        if content.startswith("["):
            continue
        if isinstance(msg, HumanMessage):
            context.append(msg)
        elif isinstance(msg, AIMessage):
            context.append(msg)
    return context


async def _run_agent_with_tools(
    llm,
    messages: list,
    tools: list,
    max_iterations: int = 5,
    agent_name: str = "agent",
) -> Any:
    """ReAct tool-calling loop: LLM → tool calls → LLM → ... → final response."""
    tool_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    for iteration in range(max_iterations):
        result = await llm_with_tools.ainvoke(messages)

        if not result.tool_calls:
            logger.info(f"   [{agent_name}] Final response at iteration {iteration + 1}")
            return result

        logger.info(f"   [{agent_name}] Iteration {iteration + 1}: {len(result.tool_calls)} tool call(s)")
        messages.append(result)

        for tool_call in result.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call.get("id", tool_name)

            logger.info(f"   [{agent_name}] Calling: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")

            tool_fn = tool_map.get(tool_name)
            if tool_fn:
                try:
                    tool_result = await tool_fn.ainvoke(tool_args)
                    tool_result_str = json.dumps(tool_result, default=str, ensure_ascii=False)
                    if len(tool_result_str) > 4000:
                        tool_result_str = tool_result_str[:4000] + "...(truncated)"
                    messages.append(ToolMessage(content=tool_result_str, tool_call_id=tool_id))
                except Exception as e:
                    logger.error(f"   [{agent_name}] Tool {tool_name} error: {e}")
                    messages.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_id))
            else:
                messages.append(ToolMessage(content=f"Unknown tool: {tool_name}", tool_call_id=tool_id))

    logger.warning(f"   [{agent_name}] Max iterations reached, forcing final response")
    result = await llm.ainvoke(messages)
    return result


