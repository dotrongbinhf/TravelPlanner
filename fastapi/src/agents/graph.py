"""
LangGraph StateGraph — Native Parallel Fan-out.

Graph topology:
  START → orchestrator → [conditional fan-out]
    ├─ (greeting/clarification/general) → END
    └─ (plan_creation) →  flight ─────────┐
                           hotel ─────────┤→ itinerary → restaurant ──┐→ synthesize → END
                           attraction────┤              preparation ┘
                           weather_fetch─┘

Phase 1: Flight + Attraction + Hotel + Weather run in parallel (native LangGraph fan-out).
Itinerary: Weather-aware LLM scheduling with resolved places.
Phase 2: Restaurant + Preparation run in parallel (native LangGraph fan-out).
Synthesize: Compiles all data and aggregated costs into final response.
"""
import logging
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.agents.state import GraphState
# Non-VRP LLM version:
from src.agents.nodes import orchestrator_nonVRP_node as orchestrator_node
from src.agents.nodes import itinerary_nonVRP_agent_node as itinerary_agent_node

from src.agents.nodes import (
    hotel_agent_node,
    flight_agent_node,
    attraction_agent_node,
    restaurant_agent_node,
    preparation_agent_node,
    synthesize_agent_node,
    weather_fetch_node,
)

logger = logging.getLogger(__name__)


def route_from_orchestrator(state: GraphState) -> str | list[str]:
    """Route from orchestrator: fan-out to Phase 1 agents or direct to END."""
    if state.get("final_response"):
        logger.info("🔀 [ROUTER] Orchestrator → END (has final_response)")
        return END

    plan = state.get("orchestrator_plan", {})
    tasks = plan.get("tasks", [])
    intent = plan.get("intent", "greeting")

    if intent in ("greeting", "clarification_needed", "general") or not tasks:
        logger.info("🔀 [ROUTER] Orchestrator → END (simple/general query)")
        return END

    logger.info(f"🔀 [ROUTER] Orchestrator → Phase 1 fan-out [flight, hotel, attraction, weather] (tasks: {tasks})")
    return ["flight", "hotel", "attraction", "weather"]


def build_agent_graph(use_checkpointer: bool = True):
    """Build the graph with native LangGraph parallel fan-out.

    Phase 1: flight + hotel + attraction + weather run in parallel (fan-out from orchestrator).
              Each agent self-skips if no context is provided.
    Itinerary: Runs after all Phase 1 agents complete (fan-in). Weather-aware scheduling.
    Phase 2: restaurant + preparation run in parallel (fan-out from itinerary).
    Synthesize: Runs after all Phase 2 agents complete (fan-in).
    """
    logger.info("Building LangGraph workflow (native parallel fan-out)...")

    graph = StateGraph(GraphState)

    # ── Register individual agent nodes ────────────────────────────
    graph.add_node("orchestrator", orchestrator_node)

    # Phase 1 agents (will run in parallel via fan-out edges)
    graph.add_node("flight", flight_agent_node)
    graph.add_node("hotel", hotel_agent_node)
    graph.add_node("attraction", attraction_agent_node)
    graph.add_node("weather", weather_fetch_node)

    # Sequential: itinerary scheduling
    graph.add_node("itinerary", itinerary_agent_node)

    # Phase 2 agents (will run in parallel via fan-out edges)
    graph.add_node("restaurant", restaurant_agent_node)
    graph.add_node("preparation", preparation_agent_node)

    # Final: synthesize all results
    graph.add_node("synthesize", synthesize_agent_node)

    # ── Entry ──────────────────────────────────────────────────────
    graph.add_edge(START, "orchestrator")

    # ── Conditional fan-out from orchestrator ──────────────────────
    # Returns END for simple queries, or ["flight","hotel","attraction","weather"]
    # for plan creation — LangGraph runs all 4 in parallel (superstep).
    graph.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        ["flight", "hotel", "attraction", "weather", END],
    )

    # ── Phase 1 fan-in: all 4 agents → itinerary ──────────────────
    # LangGraph waits for ALL fan-out branches to complete before
    # running the next node (itinerary) in the following superstep.
    graph.add_edge("flight", "itinerary")
    graph.add_edge("hotel", "itinerary")
    graph.add_edge("attraction", "itinerary")
    graph.add_edge("weather", "itinerary")

    # ── Phase 2 fan-out: itinerary → restaurant + preparation ─────
    # Both run in parallel after itinerary completes.
    graph.add_edge("itinerary", "restaurant")
    graph.add_edge("itinerary", "preparation")

    # ── Phase 2 fan-in: both → synthesize ─────────────────────────
    graph.add_edge("restaurant", "synthesize")
    graph.add_edge("preparation", "synthesize")

    # ── Final ─────────────────────────────────────────────────────
    graph.add_edge("synthesize", END)

    # ── Compile ───────────────────────────────────────────────────
    # memory = MemorySaver()
    # compiled = graph.compile(checkpointer=memory)

    # # ── Log graph structure ───────────────────────────────────────
    # logger.info("✅ LangGraph compiled (native parallel fan-out)")
    # logger.info("   Flow: orchestrator → [flight | hotel | attraction | weather] → itinerary → [restaurant | preparation] → synthesize → END")

    # return compiled

    if use_checkpointer:
        return graph.compile(checkpointer=MemorySaver())
    else:
        return graph.compile()

# command to run: py -c "from src.agents.graph import save_graph_image; save_graph_image('graph.png')"
def save_graph_image(output_path: str = "graph.png"):
    """Save the compiled graph as a PNG image for visualization.

    Uses Mermaid.ink API (requires internet).
    Usage: from src.agents.graph import save_graph_image; save_graph_image()
    """
    try:
        png_data = compiled_graph.get_graph().draw_mermaid_png()
        with open(output_path, "wb") as f:
            f.write(png_data)
        logger.info(f"📊 Graph image saved to {output_path}")
        print(f"✅ Graph image saved to {output_path}")
    except Exception as e:
        logger.error(f"❌ Could not save graph image: {e}")
        print(f"❌ Could not save graph image: {e}")


# Pre-built compiled graph
compiled_graph = build_agent_graph()

studio_graph = build_agent_graph(use_checkpointer=False)
