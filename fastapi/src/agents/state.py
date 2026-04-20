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
    other agents' results. This enables parallel agents to write concurrently.
    If 'clear_all' is present and True in new, the existing dict is wiped first."""
    if existing is None:
        existing = {}
    if new is None:
        return existing
        
    merged = {**existing}
    if new.get("clear_all") is True:
        merged = {}
        new = {k: v for k, v in new.items() if k != "clear_all"}
        
    merged.update(new)
    return merged


class GraphState(TypedDict):
    """
    Shared state for the LangGraph multi-agent workflow.

    Fields:
        conversation_id: Unique ID of the conversation (maps to MemorySaver thread_id).
        plan_id: ID of the plan being discussed/modified.
        messages: LangChain message history, auto-appended via add_messages reducer.
        
        # Intent + Macro Planning
        routed_intent: Intent classification from Intent Agent (e.g. "draft_plan").
        user_context: Extracted user preferences/requirements from conversation.
        macro_plan: Structured plan from Macro Planning — plan_context, tasks, per-agent contexts.
        
        # Agent results (uses merge reducer for safe parallel writes)
        agent_outputs: Accumulated outputs from each agent, keyed by agent name.
        
        # Conversational state
        current_plan: Accumulated trip context across turns — itinerary, budget,
                      packing, notes, plan_context, last_suggestions. Updated every
                      turn by Intent Agent (context changes) and pipeline outputs.
        
        # Final output
        final_response: The final response text to send back to the user.
        structured_output: Structured JSON data for UI updates (plan sections).
        
        metadata: Flexible metadata dict.
    """

    conversation_id: str
    plan_id: str
    messages: Annotated[list, add_messages]

    # Intent + Macro Planning
    routed_intent: str
    last_intent: dict[str, Any]  # Full output dict from Intent Agent (contains user_request_rewrite, etc.)
    user_context: dict[str, Any]
    macro_plan: dict[str, Any]

    # Agent results (merge reducer for parallel safety)
    agent_outputs: Annotated[dict[str, Any], merge_agent_outputs]

    # Conversational state
    current_plan: dict[str, Any]
    constraint_overrides: dict[str, Any]  # User-provided flight/hotel time overrides for modify mode
    selection_update: dict[str, Any]  # Hotel/flight selection from select_and_apply node (for itinerary rerange)

    # Final output
    final_response: str
    structured_output: dict[str, Any]

    metadata: dict[str, Any]

