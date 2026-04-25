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
# Helper Functions
# ============================================================

def _extract_json(text_or_list: Any) -> dict:
    """Extract JSON from LLM response text, handling markdown code blocks and list content."""
    text = ""
    # Handle case where Gemini returns a list of parts instead of a string
    if isinstance(text_or_list, list):
        for part in text_or_list:
            if isinstance(part, dict) and "text" in part:
                text += part["text"]
            elif isinstance(part, str):
                text += part
    elif isinstance(text_or_list, dict):
        if "text" in text_or_list:
            text = text_or_list["text"]
        else:
            return text_or_list 
    else:
        text = str(text_or_list)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if "```json" in text:
        start = text.index("```json") + 7
        end = text.rindex("```")
        return json.loads(text[start:end].strip())

    if "```" in text:
        start = text.index("```") + 3
        end = text.rindex("```")
        return json.loads(text[start:end].strip())

    start = text.find("{")
    if start >= 0:
        end = text.rfind("}") + 1
        while end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                end = text.rfind("}", 0, end - 1) + 1

    raise ValueError(f"No valid JSON found in LLM response: {text[:200]}...")

# Messages List -> Only Latest user message
# def _get_latest_user_message(state: GraphState) -> str:
#     """Extract the most recent user message from state."""
#     messages = state.get("messages", [])
#     for msg in reversed(messages):
#         if isinstance(msg, HumanMessage):
#             return msg.content
#     return ""


# def _get_conversation_context(state: GraphState, max_messages: int = 10) -> list:
#     """Build conversation context from message history."""
#     messages = state.get("messages", [])
#     context = []
#     for msg in messages[-max_messages:]:
#         content = msg.content if hasattr(msg, "content") else str(msg)
#         if content.startswith("["):
#             continue
#         if isinstance(msg, HumanMessage):
#             context.append(msg)
#         elif isinstance(msg, AIMessage):
#             context.append(msg)
#     return context



MAX_TOOL_MESSAGE_CHARS = 4000

def _truncate_tool_result(tool_result_str: str) -> str:
    """Truncate tool result for LLM context while keeping it useful.
    Full results are preserved in tool_logs for programmatic extraction."""
    if len(tool_result_str) <= MAX_TOOL_MESSAGE_CHARS:
        return tool_result_str
    return tool_result_str[:MAX_TOOL_MESSAGE_CHARS] + "\n...[TRUNCATED for context window — full data saved in tool_logs]"


async def _run_agent_with_tools(
    llm,
    messages: list,
    tools: list,
    max_iterations: int = 5,
    agent_name: str = "agent",
    slim_tool_output: callable = None,
) -> tuple[Any, list[dict]]:
    """ReAct tool-calling loop: LLM → tool calls → LLM → ... → final response.
    
    When the LLM emits multiple tool calls in a single turn, they are executed
    concurrently via asyncio.gather for faster results.
    
    Args:
        slim_tool_output: Optional function(tool_result: dict) -> dict that
            reduces tool output before sending to LLM. Full output is always
            preserved in tool_logs for programmatic use.
    
    Returns:
        A tuple of (final_llm_result, tool_logs) where tool_logs is a list of
        dicts with keys: name, input, output.
    """
    import asyncio

    tool_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)
    tool_logs: list[dict] = []

    for iteration in range(max_iterations):
        result = await llm_with_tools.ainvoke(messages)

        if not result.tool_calls:
            logger.info(f"   [{agent_name}] Final response at iteration {iteration + 1}")
            return result, tool_logs

        num_calls = len(result.tool_calls)
        logger.info(f"   [{agent_name}] Iteration {iteration + 1}: {num_calls} tool call(s)")
        messages.append(result)

        if num_calls == 1:
            # Single tool call — execute directly (no gather overhead)
            tool_call = result.tool_calls[0]
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call.get("id", tool_name)

            logger.info(f"   [{agent_name}] Calling: {tool_name}({json.dumps(tool_args, ensure_ascii=False)[:200]})")

            tool_fn = tool_map.get(tool_name)
            if tool_fn:
                try:
                    tool_result = await tool_fn.ainvoke(tool_args)
                    tool_logs.append({"name": tool_name, "input": tool_args, "output": tool_result})
                    # Slim for LLM context if callback provided, keep full in tool_logs
                    llm_result = slim_tool_output(tool_result) if slim_tool_output else tool_result
                    llm_result_str = json.dumps(llm_result, default=str, ensure_ascii=False)
                    messages.append(ToolMessage(content=_truncate_tool_result(llm_result_str), tool_call_id=tool_id))
                except Exception as e:
                    logger.error(f"   [{agent_name}] Tool {tool_name} error: {e}")
                    tool_logs.append({"name": tool_name, "input": tool_args, "output": {"error": str(e)}})
                    messages.append(ToolMessage(content=f"Error: {str(e)}", tool_call_id=tool_id))
            else:
                messages.append(ToolMessage(content=f"Unknown tool: {tool_name}", tool_call_id=tool_id))
        else:
            # Multiple tool calls — execute in parallel with asyncio.gather
            logger.info(f"   [{agent_name}] Executing {num_calls} tool calls in parallel")

            async def _execute_tool(tc: dict) -> tuple[dict, str, str | None]:
                """Execute a single tool call, return (log_entry, result_str, tool_id)."""
                t_name = tc["name"]
                t_args = tc["args"]
                t_id = tc.get("id", t_name)

                logger.info(f"   [{agent_name}] Calling: {t_name}({json.dumps(t_args, ensure_ascii=False)[:200]})")

                t_fn = tool_map.get(t_name)
                if not t_fn:
                    return (
                        {"name": t_name, "input": t_args, "output": {"error": "Unknown tool"}},
                        f"Unknown tool: {t_name}",
                        t_id,
                    )
                try:
                    t_result = await t_fn.ainvoke(t_args)
                    # Slim for LLM context if callback provided
                    t_llm_result = slim_tool_output(t_result) if slim_tool_output else t_result
                    t_llm_result_str = json.dumps(t_llm_result, default=str, ensure_ascii=False)
                    return (
                        {"name": t_name, "input": t_args, "output": t_result},
                        t_llm_result_str,
                        t_id,
                    )
                except Exception as e:
                    logger.error(f"   [{agent_name}] Tool {t_name} error: {e}")
                    return (
                        {"name": t_name, "input": t_args, "output": {"error": str(e)}},
                        f"Error: {str(e)}",
                        t_id,
                    )

            # Run all tool calls concurrently
            results = await asyncio.gather(
                *[_execute_tool(tc) for tc in result.tool_calls]
            )

            # Append results in original order (important for LLM context)
            for log_entry, result_str, tool_id in results:
                tool_logs.append(log_entry)
                messages.append(ToolMessage(content=_truncate_tool_result(result_str), tool_call_id=tool_id))

    logger.warning(f"   [{agent_name}] Max iterations reached, forcing final response")
    result = await llm.ainvoke(messages)
    return result, tool_logs


