"""
LangGraph StateGraph — Intent-based Dynamic Routing.

Graph topology (v8):
  START → intent → [conditional]
    ├─ (greeting/clarification/general) → END
    ├─ (draft_plan) → orchestrator → [attraction, weather] → itinerary → [preparation] → synthesize → END
    ├─ (full_plan)  → orchestrator → [flight, hotel, attraction, weather] → itinerary → [restaurant, preparation] → synthesize → END
    ├─ (search_flights/hotels/attractions/restaurants) → agent → synthesize → END
    ├─ (preparation_inquiry) → preparation → synthesize → END
    ├─ (modify_itinerary) → itinerary → synthesize → END
    ├─ (select_flight/select_hotel) → select_apply → [itinerary → synthesize] or END
    └─ (modify_plan) → orchestrator → ... → synthesize → END  [Phase 2]

Phase 1: Intent-based routing with draft/full pipeline + itinerary modification.
Phase 2 (future): Full plan modifications.

Checkpointer: AsyncPostgresSaver for state persistence across server restarts.
"""
import logging
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.config import settings

from src.agents.state import GraphState

# Node imports
from src.agents.nodes import intent_agent_node
from src.agents.nodes import orchestrator_node
from src.agents.nodes import itinerary_agent_node
from src.agents.nodes import (
    hotel_agent_node,
    flight_agent_node,
    attraction_agent_node,
    restaurant_agent_node,
    preparation_agent_node,
    synthesize_agent_node,
    weather_fetch_node,
)
from src.agents.nodes.select_apply import select_and_apply_node

logger = logging.getLogger(__name__)


# ── Route functions ────────────────────────────────────────────────────

def route_from_intent(state: GraphState) -> str | list[str]:
    """Route from Intent Agent based on detected intent."""
    # If intent already produced a direct response, go to END
    if state.get("final_response"):
        logger.info("🔀 [ROUTER] Intent → END (has final_response)")
        return END

    intent = (state.get("intent_output") or {}).get("intent", "general")

    if intent in ("general", "clarification_needed"):
        logger.info(f"🔀 [ROUTER] Intent → END ({intent})")
        return END

    if intent in ("draft_plan", "full_plan", "modify_plan"):
        logger.info(f"🔀 [ROUTER] Intent → orchestrator ({intent})")
        return ["orchestrator"]

    if intent == "preparation_inquiry":
        logger.info("🔀 [ROUTER] Intent → preparation (standalone inquiry)")
        return ["preparation"]

    if intent == "modify_itinerary":
        # Itinerary Agent handles ALL modifications (including new attraction suggestions)
        logger.info("🔀 [ROUTER] Intent → itinerary (modify_itinerary)")
        return ["itinerary"]

    # Selection from search results
    if intent in ("select_flight", "select_hotel", "select_restaurant"):
        logger.info(f"🔀 [ROUTER] Intent → select_apply ({intent})")
        return ["select_apply"]

    # Standalone agent routing
    agent_map = {
        "search_flights": ["flight"],
        "search_hotels": ["hotel"],
        "suggest_attractions": ["attraction"],
        "search_restaurants": ["restaurant"],
    }
    route = agent_map.get(intent)
    if route:
        logger.info(f"🔀 [ROUTER] Intent → {route} (standalone)")
        return route

    logger.warning(f"🔀 [ROUTER] Intent → END (unknown intent: {intent})")
    return END


def route_from_orchestrator(state: GraphState) -> str | list[str]:
    """Route from Orchestrator: fan-out to Phase 1 agents based on intent."""
    if state.get("final_response"):
        logger.info("🔀 [ROUTER] Orchestrator → END (has final_response)")
        return END

    intent = (state.get("intent_output") or {}).get("intent", "")
    plan = state.get("macro_plan", {})
    tasks = plan.get("task_list", [])

    if not tasks:
        logger.info("🔀 [ROUTER] Orchestrator → END (no tasks generated)")
        return END

    if intent == "draft_plan":
        # Draft mode: only attraction + weather (skip flight, hotel)
        logger.info("🔀 [ROUTER] Orchestrator → [attraction, weather] (DRAFT)")
        return ["attraction", "weather"]
    else:
        # Full mode: all Phase 1 agents
        agents = ["attraction", "weather"]
        if "flight" in tasks:
            agents.append("flight")
        if "hotel" in tasks:
            agents.append("hotel")
        logger.info(f"🔀 [ROUTER] Orchestrator → {agents} (FULL, tasks: {tasks})")
        return agents


def route_from_itinerary(state: GraphState) -> list[str]:
    """Route from Itinerary: fan-out to Phase 2 agents or synthesize."""
    intent = (state.get("intent_output") or {}).get("intent", "")

    if intent in ("modify_itinerary", "select_hotel", "select_flight"):
        # Modify or selection-triggered rerange: skip Phase 2, go directly to synthesize
        logger.info(f"🔀 [ROUTER] Itinerary → [synthesize] ({intent})")
        return ["synthesize"]
    elif intent == "draft_plan":
        # Draft: only preparation (skip restaurant)
        logger.info("🔀 [ROUTER] Itinerary → [preparation] (DRAFT)")
        return ["preparation"]
    else:
        # Full: restaurant + preparation in parallel
        logger.info("🔀 [ROUTER] Itinerary → [restaurant, preparation] (FULL)")
        return ["restaurant", "preparation"]


def route_from_select_apply(state: GraphState) -> str:
    """Route from select_apply: rerange → itinerary, or END (direct response)."""
    # If select_apply already set final_response (no itinerary to rerange)
    if state.get("final_response"):
        logger.info("🔀 [ROUTER] Select Apply → END (direct response, no itinerary)")
        return END

    constraint_overrides = state.get("constraint_overrides", {})
    if constraint_overrides.get("needs_rerange"):
        logger.info("🔀 [ROUTER] Select Apply → itinerary (rerange needed)")
        return "itinerary"

    logger.info("🔀 [ROUTER] Select Apply → synthesize (no rerange)")
    return "synthesize"


def route_from_phase1_agent(state: GraphState) -> str:
    """Route Phase 1 agents: pipeline → itinerary, standalone → synthesize."""
    plan = state.get("macro_plan", {})
    if plan.get("task_list"):
        return "itinerary"   # Pipeline mode
    return "synthesize"      # Standalone mode


# ── Build graph ────────────────────────────────────────────────────────

async def build_agent_graph(checkpointer=None):
    """Build the graph with intent-based dynamic routing.

    Intent Agent: Lightweight routing + context tracking.
    Orchestrator (Macro Planning): Creates structured plan for agents.
    Phase 1: flight + hotel + attraction + weather (parallel fan-out, intent-dependent).
    Itinerary: Weather-aware LLM scheduling with resolved places.
    Phase 2: restaurant + preparation (parallel fan-out, intent-dependent).
    Synthesize: Compiles all data into final response.

    Checkpointer: AsyncPostgresSaver for state persistence.
    """
    logger.info("Building LangGraph workflow (intent-based routing v8)...")

    graph = StateGraph(GraphState)

    # ── Register nodes ─────────────────────────────────────────────
    graph.add_node("intent", intent_agent_node)
    graph.add_node("orchestrator", orchestrator_node)

    # Phase 1 agents
    graph.add_node("flight", flight_agent_node)
    graph.add_node("hotel", hotel_agent_node)
    graph.add_node("attraction", attraction_agent_node)
    graph.add_node("weather", weather_fetch_node)

    # Sequential: itinerary scheduling
    graph.add_node("itinerary", itinerary_agent_node)

    # Phase 2 agents
    graph.add_node("restaurant", restaurant_agent_node)
    graph.add_node("preparation", preparation_agent_node)

    # Final: synthesize
    graph.add_node("synthesize", synthesize_agent_node)

    # Selection: select_apply (flight/hotel selection from search results)
    graph.add_node("select_apply", select_and_apply_node)

    # ── Entry ──────────────────────────────────────────────────────
    graph.add_edge(START, "intent")

    # ── Intent → conditional routing ───────────────────────────────
    graph.add_conditional_edges(
        "intent",
        route_from_intent,
        ["orchestrator", "preparation", "flight", "hotel", "attraction", "restaurant", "itinerary", "select_apply", END],
    )

    # ── Orchestrator → conditional fan-out ─────────────────────────
    graph.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        ["flight", "hotel", "attraction", "weather", END],
    )

    # ── Phase 1 fan-in: conditional (pipeline → itinerary, standalone → synthesize)
    graph.add_conditional_edges("flight", route_from_phase1_agent, ["itinerary", "synthesize"])
    graph.add_conditional_edges("hotel", route_from_phase1_agent, ["itinerary", "synthesize"])
    graph.add_conditional_edges("attraction", route_from_phase1_agent, ["itinerary", "synthesize"])
    graph.add_edge("weather", "itinerary")  # Weather is always pipeline-only

    # ── Itinerary → conditional Phase 2 fan-out ────────────────────
    graph.add_conditional_edges(
        "itinerary",
        route_from_itinerary,
        ["restaurant", "preparation", "synthesize"],
    )

    # ── Phase 2 fan-in → synthesize ────────────────────────────────
    graph.add_edge("restaurant", "synthesize")
    graph.add_edge("preparation", "synthesize")

    # ── Preparation standalone → synthesize (for preparation_inquiry) ──
    # Note: preparation already has edge to synthesize from Phase 2.
    # LangGraph handles this — if preparation runs standalone via intent,
    # it flows to synthesize. If it runs from itinerary, same edge applies.

    # ── Select Apply → conditional (itinerary or END) ──────────────
    graph.add_conditional_edges(
        "select_apply",
        route_from_select_apply,
        ["itinerary", "synthesize", END],
    )

    # ── Final ──────────────────────────────────────────────────────
    graph.add_edge("synthesize", END)

    # ── Compile ────────────────────────────────────────────────────
    if checkpointer:
        compiled = graph.compile(checkpointer=checkpointer)
        logger.info("✅ LangGraph compiled (intent-based routing v8, PostgresSaver)")
    else:
        compiled = graph.compile()
        logger.info("✅ LangGraph compiled (intent-based routing v8, NO checkpointer)")

    logger.info("   Flow: intent → [orchestrator] → [agents] → itinerary → [agents] → synthesize → END")
    return compiled

# command to run: py -c "import asyncio; from src.agents.graph import save_graph_image; asyncio.run(save_graph_image('graph.png'))"
# or to mermaid: py -c "import asyncio; from src.agents.graph import build_agent_graph; g=asyncio.run(build_agent_graph()); open('graph.mmd','w',encoding='utf-8').write(g.get_graph().draw_mermaid())"
async def save_graph_image(output_path: str = "graph.png"):
    """Save the compiled graph as a PNG image for visualization.
    """
    try:
        graph = await build_agent_graph()
        png_data = graph.get_graph().draw_mermaid_png()
        with open(output_path, "wb") as f:
            f.write(png_data)
        logger.info(f"📊 Graph image saved to {output_path}")
        print(f"✅ Graph image saved to {output_path}")
    except Exception as e:
        logger.error(f"❌ Could not save graph image: {e}")
        print(f"❌ Could not save graph image: {e}")


# Pre-built compiled graph — initialized at app startup via init_graph()
compiled_graph = None


async def init_graph(checkpointer=None):
    """Initialize the compiled graph. Must be called during app startup (async context)."""
    global compiled_graph
    compiled_graph = await build_agent_graph(checkpointer=checkpointer)
    return compiled_graph
