"""
GraphState definition for the Multi AI Agent system.

Defines the shared state that flows through all agent nodes in the LangGraph workflow.
Uses `add_messages` reducer for automatic message history management.
"""

from typing import Any, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class GraphState(TypedDict):
    """
    Shared state for the LangGraph multi-agent workflow.

    Fields:
        conversation_id: Unique ID of the conversation (maps to MemorySaver thread_id).
        messages: LangChain message history, auto-appended via add_messages reducer.
        current_agent: Name of the agent currently executing.
        current_tool: Name of the tool currently being used by the active agent.
        agent_outputs: Accumulated outputs from each agent, keyed by agent name.
        dotnet_api_response: Response data from the .NET backend API call.
        final_response: The final assembled response text to send back to the user.
        plan_needs_research: Routing flag — True if planner decides research is needed.
        plan_needs_details: Routing flag — True if planner decides .NET API details are needed.
        metadata: Flexible metadata dict (user preferences, plan info, etc.).
    """

    conversation_id: str
    messages: Annotated[list, add_messages]
    current_agent: str
    current_tool: str
    agent_outputs: dict[str, Any]
    dotnet_api_response: dict[str, Any]
    final_response: str
    plan_needs_research: bool
    plan_needs_details: bool
    metadata: dict[str, Any]
