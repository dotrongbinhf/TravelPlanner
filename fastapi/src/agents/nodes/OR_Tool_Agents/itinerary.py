import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.state import GraphState
from src.services.itinerary_builder import run_itinerary_pipeline
from src.agents.nodes.utils import _extract_json
from src.config import settings

llm_itinerary = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.5,
    streaming=False,
)

logger = logging.getLogger(__name__)


POST_VRP_REVIEW_SYSTEM = """You are the Itinerary Review Agent. You receive a VRP-optimized multi-day travel schedule and review it for quality.

## Your Input
- The VRP result JSON with days, stops, timing, and dropped locations
- The plan_context with trip info (travelers, pace, children, etc.)
- The mobility_plan describing arrival/departure logistics

## Your Task
Analyze the schedule and output a JSON with your assessment and any adjustments.

## What to Check
1. **Long waits (> 60 min)**: If a stop has wait > 60 min before it, suggest extending the previous attraction's visit time or adding a note (e.g., "free time for coffee/strolling nearby")
2. **Dropped must-visit places**: If any must_visit attraction was dropped, flag as critical issue
3. **Schedule flow**: Does the order feel natural? (e.g., not visiting a morning market in the afternoon)
4. **Last day logistics**: Is there enough time for checkout + activities + getting to airport?

## Response Format
CRITICAL: Your response must be one and ONLY one valid JSON object.

{
    "quality": "good | needs_adjustment",
    "adjustments": [
        {
            "day": 1,
            "type": "extend_duration | add_note | flag_dropped",
            "stop_name": "...",
            "detail": "Extend visit by 30 min to reduce 90-min wait before dinner"
        }
    ],
    "rerun_vrp": false,
    "notes": "Overall the schedule looks balanced for a relaxed family trip."
}

## Rules
- rerun_vrp should be true ONLY if a must_visit was dropped or if the schedule is fundamentally broken
- For minor wait issues, just add notes/adjustments — do NOT rerun
- Keep adjustments practical and traveler-friendly
- Be concise
"""


async def _llm_review_vrp(
    vrp_result: dict[str, Any],
    plan_context: dict[str, Any],
) -> dict[str, Any]:
    """Post-VRP LLM review: analyze schedule quality and suggest adjustments."""
    try:
        # Build a compact summary for LLM
        summary_lines = []
        for day_data in vrp_result.get("days", []):
            day_stops = []
            for stop in day_data.get("stops", []):
                info = f"{stop['arrival']} {stop['name']} ({stop['duration']}p)"
                if stop.get("wait", 0) > 0:
                    info += f" [WAIT {stop['wait']}p]"
                day_stops.append(info)
            summary_lines.append(f"Day {day_data['day']}: {' → '.join(day_stops)}")

        dropped_info = vrp_result.get("dropped", [])

        human_content = f"""VRP Schedule Result:
{chr(10).join(summary_lines)}

Dropped locations: {json.dumps(dropped_info, ensure_ascii=False) if dropped_info else "None"}

Plan context:
- Pace: {plan_context.get('pace', 'moderate')}
- Travelers: {plan_context.get('adults', 2)} adults, {plan_context.get('children', 0)} children
- Mobility plan: {plan_context.get('mobility_plan', 'N/A')}

Please review this schedule and provide your assessment."""

        messages = [
            SystemMessage(content=POST_VRP_REVIEW_SYSTEM),
            HumanMessage(content=human_content),
        ]

        result = await llm_itinerary.ainvoke(messages)
        review = _extract_json(result.content)

        logger.info(f"   [ITINERARY_REVIEW] Quality: {review.get('quality')}, "
                     f"Adjustments: {len(review.get('adjustments', []))}, "
                     f"Rerun: {review.get('rerun_vrp', False)}")
        return review

    except Exception as e:
        logger.error(f"   [ITINERARY_REVIEW] Error: {e}", exc_info=True)
        return {"quality": "good", "adjustments": [], "rerun_vrp": False, "notes": f"Review skipped: {e}"}


def _apply_adjustments(vrp_result: dict, review: dict) -> dict:
    """Apply LLM review adjustments to the VRP result (notes, duration extensions)."""
    adjustments = review.get("adjustments", [])
    if not adjustments:
        return vrp_result

    for adj in adjustments:
        day_num = adj.get("day")
        stop_name = adj.get("stop_name", "")
        adj_type = adj.get("type", "")
        detail = adj.get("detail", "")

        if not day_num:
            continue

        # Find the matching day
        for day_data in vrp_result.get("days", []):
            if day_data["day"] != day_num:
                continue

            for stop in day_data.get("stops", []):
                if stop_name and stop_name.lower() not in stop.get("name", "").lower():
                    continue

                if adj_type == "add_note":
                    stop["note"] = detail
                elif adj_type == "extend_duration":
                    stop["note"] = detail
                elif adj_type == "flag_dropped":
                    pass  # Already in dropped list

    vrp_result["review_notes"] = review.get("notes", "")
    return vrp_result


async def itinerary_agent_node(state: GraphState) -> dict[str, Any]:
    """Itinerary Agent — Builds VRP input, solves, and reviews the schedule.
    
    2-Phase Flow:
        Phase 1: run_itinerary_pipeline() → Extract places → Resolve → Build VRP → Solve
        Phase 2: LLM review → Apply adjustments (or re-run VRP if critical)
    """
    logger.info("=" * 60)
    logger.info("📅 [ITINERARY_AGENT] Node entered")

    agent_outputs = state.get("agent_outputs", {})
    plan = state.get("orchestrator_plan", {})
    plan_context = plan.get("plan_context", {})

    itinerary_result = {}

    try:
        # Phase 1: Build & Solve VRP
        logger.info("📅 [ITINERARY_AGENT] Phase 1: Building and solving VRP...")
        itinerary_result = await run_itinerary_pipeline(agent_outputs, plan)

        # Phase 2: LLM Review (only if VRP succeeded)
        # if not itinerary_result.get("error") and itinerary_result.get("days"):
        #     logger.info("📅 [ITINERARY_AGENT] Phase 2: LLM review...")
        #     review = await _llm_review_vrp(itinerary_result, plan_context)

        #     if review.get("rerun_vrp"):
        #         # Critical issue found — re-run VRP (same input, solver may find different solution with more time)
        #         logger.info("📅 [ITINERARY_AGENT] Rerunning VRP (critical review issue)...")
        #         itinerary_result = await run_itinerary_pipeline(agent_outputs, plan)

        #     # Apply adjustments (notes, duration extensions)
        #     itinerary_result = _apply_adjustments(itinerary_result, review)

    except Exception as e:
        logger.error(f"   ❌ Itinerary Agent error: {e}", exc_info=True)
        itinerary_result = {"error": True, "message": str(e), "days": [], "dropped": []}

    num_days = len(itinerary_result.get("days", []))
    dropped = len(itinerary_result.get("dropped", []))

    logger.info(f"📅 [ITINERARY_AGENT] Completed: {num_days} days, {dropped} dropped")
    logger.info("=" * 60)

    return {
        "agent_outputs": {"itinerary_agent": itinerary_result},
        "messages": [AIMessage(content=f"[Itinerary Agent] Created {num_days}-day optimized schedule ({dropped} places dropped)")],
    }
