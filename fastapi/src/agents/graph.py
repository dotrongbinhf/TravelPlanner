"""
LangGraph StateGraph definition with MemorySaver and Conditional Edges.

Builds the multi-agent workflow graph:
  __start__ → planner_node → [conditional routing] → researcher/dotnet/response
  researcher/dotnet → planner_node (loop back)
  response → __end__

Uses MemorySaver for automatic conversation memory management per thread_id.
"""

import logging
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.agents.state import GraphState
from src.agents.nodes import (
    planner_node,
    researcher_node,
    dotnet_integration_node,
    response_node,
)

logger = logging.getLogger(__name__)


def route_from_planner(state: GraphState) -> str:
    """
    Conditional routing function from planner_node.

    Examines routing flags set by the planner to decide the next node:
    - plan_needs_research → researcher_node
    - plan_needs_details → dotnet_integration_node
    - neither → response_node (direct response, e.g. greetings)
    """
    needs_research = state.get("plan_needs_research", False)
    needs_details = state.get("plan_needs_details", False)

    if needs_research:
        logger.info("🔀 [ROUTER] Planner → Researcher (needs research)")
        return "researcher"
    elif needs_details:
        logger.info("🔀 [ROUTER] Planner → DotNet Integration (needs details)")
        return "dotnet_integration"
    else:
        logger.info("🔀 [ROUTER] Planner → Response (direct response)")
        return "response"


def build_agent_graph() -> StateGraph:
    """
    Build and compile the multi-agent StateGraph.

    Returns:
        Compiled StateGraph with MemorySaver checkpointer.
    """
    logger.info("Building LangGraph multi-agent workflow...")

    # Create the graph
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("dotnet_integration", dotnet_integration_node)
    graph.add_node("response", response_node)

    # Entry point
    graph.add_edge(START, "planner")

    # Conditional edges from planner
    graph.add_conditional_edges(
        "planner",
        route_from_planner,
        {
            "researcher": "researcher",
            "dotnet_integration": "dotnet_integration",
            "response": "response",
        },
    )

    # Sub-agents loop back to planner after completion
    graph.add_edge("researcher", "planner")
    graph.add_edge("dotnet_integration", "planner")

    # Response is the final node
    graph.add_edge("response", END)

    # Compile with MemorySaver for automatic conversation memory
    memory = MemorySaver()
    compiled = graph.compile(checkpointer=memory)

    logger.info("✅ LangGraph workflow compiled successfully")
    logger.info("   Nodes: planner, researcher, dotnet_integration, response")
    logger.info("   Checkpointer: MemorySaver (in-memory)")
    logger.info("   Conditional edges from planner based on routing flags")

    return compiled


# Pre-built compiled graph instance — import this to use
compiled_graph = build_agent_graph()
