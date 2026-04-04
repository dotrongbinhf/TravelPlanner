"""
GraphState definition for the Multi AI Agent travel planner.

Defines the shared state that flows through all agent nodes in the LangGraph workflow.
Uses `add_messages` reducer for automatic message history management and
`merge_agent_outputs` reducer so parallel agents can write concurrently.
"""

from typing import Any, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


def merge_agent_outputs(
    existing: dict[str, Any], new: dict[str, Any]
) -> dict[str, Any]:
    """Reducer: merge new agent outputs into existing dict without overwriting
    other agents' results. This enables parallel agents to write concurrently."""
    if existing is None:
        existing = {}
    if new is None:
        return existing
    merged = {**existing}
    merged.update(new)
    return merged


class GraphState(TypedDict):
    """
    Shared state for the LangGraph multi-agent workflow.

    Fields:
        conversation_id: Unique ID of the conversation (maps to MemorySaver thread_id).
        plan_id: ID of the plan being discussed/modified.
        messages: LangChain message history, auto-appended via add_messages reducer.
        
        # Orchestrator routing
        pending_tasks: Queue of agent tasks to execute next.
        completed_tasks: List of completed agent task names.
        user_context: Extracted user preferences/requirements from conversation.
        orchestrator_plan: Detailed plan with per-agent instructions from orchestrator.
        
        # Agent results (uses merge reducer for safe parallel writes)
        agent_outputs: Accumulated outputs from each agent, keyed by agent name.
        
        # Final output
        final_response: The final response text to send back to the user.
        structured_output: Structured JSON data for UI updates (plan sections).
        db_commands: List of DB operations to execute via .NET.
        
        metadata: Flexible metadata dict.
    """

    conversation_id: str
    plan_id: str
    messages: Annotated[list, add_messages]

    # Orchestrator routing
    pending_tasks: list[str]
    completed_tasks: list[str]
    user_context: dict[str, Any]
    orchestrator_plan: dict[str, Any]

    # Agent results (merge reducer for parallel safety)
    agent_outputs: Annotated[dict[str, Any], merge_agent_outputs]

    # Final output
    final_response: str
    structured_output: dict[str, Any]
    db_commands: list[dict[str, Any]]

    metadata: dict[str, Any]
