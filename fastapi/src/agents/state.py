"""
GraphState definition for the Multi AI Agent travel planner.

Defines the shared state that flows through all agent nodes in the LangGraph workflow.
Uses `merge_agent_outputs` reducer so parallel agents can write concurrently.
"""

from typing import Any, Annotated
from typing_extensions import TypedDict


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
        user_message: The latest message from the user for the current turn.
        
        # Intent + Macro Planning
        intent_output: Full output dict from Intent Agent.
        macro_plan: Structured plan from Macro Planning — plan_context, tasks, per-agent contexts.
        
        # Agent results (uses merge reducer for safe parallel writes)
        agent_outputs: Accumulated outputs from each agent, keyed by agent name.
        
        # Conversational state
        current_plan: Accumulated trip context across turns — itinerary, budget,
                      packing, notes, plan_context, last_suggestions. Updated every
                      turn by Intent Agent (context changes) and pipeline outputs.
        
        constraint_overrides: Unified constraint dict. Carries:
            - User-provided flight/hotel times (from Intent Agent)
            - Selection metadata from select_and_apply (type, needs_rerange,
              auto_user_message, hotel_name, etc.) merged alongside timing keys.
            This avoids splitting one logical "what changed" signal across two state fields.
        
        # Final output
        final_response: The final response text to send back to the user.
        structured_output: Structured JSON data for UI updates (plan sections).
        
        metadata: Flexible metadata dict.
    """

    conversation_id: str
    user_message: str

    # Intent + Macro Planning
    intent_output: dict[str, Any]  # Full output dict from Intent Agent (includes "intent" key)
    macro_plan: dict[str, Any]

    # Agent results (merge reducer for parallel safety)
    agent_outputs: Annotated[dict[str, Any], merge_agent_outputs]

    # Conversational state
    current_plan: dict[str, Any]
    constraint_overrides: dict[str, Any]  # Unified: user time constraints + selection metadata

    # Final output
    final_response: str
    structured_output: dict[str, Any]

    metadata: dict[str, Any]
