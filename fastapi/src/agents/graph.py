"""
LangGraph StateGraph — Phase 1 Testing.

Graph topology:
  START → orchestrator → [conditional routing]
    ├─ (greeting/clarification/general_query) → synthesize → END
    └─ (plan_creation/modification) → phase1_parallel [flight + attraction + hotel]
                                     → synthesize → END

Phase 1: Flight + Attraction + Hotel run in parallel (all receive Orchestrator context independently).
Restaurant, Itinerary, Preparation are disabled for now.
"""

import logging
import asyncio
from typing import Any
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.agents.state import GraphState
from src.agents.nodes import (
    orchestrator_node,
    hotel_agent_node,
    flight_agent_node,
    attraction_agent_node,
    restaurant_agent_node,
    preparation_agent_node,
    itinerary_agent_node,
    synthesize_agent_node,
)

logger = logging.getLogger(__name__)


def route_from_orchestrator(state: GraphState) -> str:
    """Route from orchestrator: parallel agents or direct to synthesize."""
    if state.get("final_response"):
        logger.info("🔀 [ROUTER] Orchestrator → Synthesize (has final_response)")
        return "synthesize"

    plan = state.get("orchestrator_plan", {})
    tasks = plan.get("tasks", [])
    intent = plan.get("intent", "greeting")

    if intent in ("greeting", "information_query", "clarification_needed", "general_query") or not tasks:
        logger.info("🔀 [ROUTER] Orchestrator → Synthesize (simple/general query)")
        return "synthesize"

    logger.info(f"🔀 [ROUTER] Orchestrator → Phase 1 (tasks: {tasks})")
    return "phase1"


async def phase1_parallel_node(state: GraphState) -> dict[str, Any]:
    """Phase 1: Flight + Attraction + Hotel agents run in parallel.
    All three receive Orchestrator context independently.
    """
    logger.info("=" * 60)
    logger.info("⚡ [PHASE 1] Flight + Attraction + Hotel (parallel)")

    plan = state.get("orchestrator_plan", {})
    tasks = plan.get("tasks", [])

    agents_to_run = {}
    if "flight" in tasks and plan.get("flight"):
        agents_to_run["flight"] = flight_agent_node
    if "attraction" in tasks and plan.get("attraction"):
        agents_to_run["attraction"] = attraction_agent_node
    if "hotel" in tasks and plan.get("hotel"):
        agents_to_run["hotel"] = hotel_agent_node

    if not agents_to_run:
        logger.info("   No Phase 1 agents to run")
        return {}

    logger.info(f"   Running: {list(agents_to_run.keys())}")

    results = await asyncio.gather(
        *[fn(state) for fn in agents_to_run.values()],
        return_exceptions=True
    )

    merged_outputs = {}
    all_messages = []
    for name, result in zip(agents_to_run.keys(), results):
        if isinstance(result, Exception):
            logger.error(f"   ❌ {name} failed: {result}")
            merged_outputs[f"{name}_agent"] = {"error": str(result)}
        elif isinstance(result, dict):
            merged_outputs.update(result.get("agent_outputs", {}))
            all_messages.extend(result.get("messages", []))

    logger.info(f"⚡ [PHASE 1] Completed: {list(merged_outputs.keys())}")
    logger.info("=" * 60)

    return {
        "agent_outputs": merged_outputs,
        "messages": all_messages,
        "current_agent": "phase1_complete",
    }


def build_agent_graph() -> StateGraph:
    """Build the Phase 1 testing graph."""
    logger.info("Building LangGraph workflow (Phase 1: Flight + Attraction + Hotel)...")

    graph = StateGraph(GraphState)

    # Register nodes
    graph.add_node("orchestrator", orchestrator_node)
    # graph.add_node("phase1_parallel", phase1_parallel_node)
    # graph.add_node("synthesize", synthesize_agent_node)

    # Entry
    graph.add_edge(START, "orchestrator")

    # Conditional routing from orchestrator
    # graph.add_conditional_edges(
    #     "orchestrator",
    #     route_from_orchestrator,
    #     {
    #         "phase1": "phase1_parallel",
    #         "synthesize": "synthesize",
    #     },
    # )

    # # Phase 1 → Synthesize → END
    # graph.add_edge("phase1_parallel", "synthesize")
    # graph.add_edge("synthesize", END)

    graph.add_edge("orchestrator", END)

    # Compile
    memory = MemorySaver()
    compiled = graph.compile(checkpointer=memory)

    logger.info("✅ LangGraph compiled (Phase 1 testing)")
    logger.info("   Flow: orchestrator → [flight+attraction+hotel] → synthesize → END")

    return compiled


# Pre-built compiled graph
compiled_graph = build_agent_graph()
