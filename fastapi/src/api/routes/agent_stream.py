"""
SSE (Server-Sent Events) endpoint for the LangGraph multi-agent system.

Provides realtime streaming of agent events to connected clients via HTTP POST + SSE.
Uses `astream_events` with version="v2" to capture granular LangGraph events
and maps them to structured AgentEvent objects sent as SSE data lines.

Endpoint: POST /api/agent/stream
"""

import json
import logging
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agents import graph as agent_graph
from src.models.events import AgentEvent, EventType

logger = logging.getLogger(__name__)

router = APIRouter()

# Track which LangGraph node names map to our frontend agent names
NODE_TO_AGENT = {
    "intent": "intent",
    "orchestrator": "orchestrator",
    "hotel": "hotel_agent",
    "flight": "flight_agent",
    "attraction": "attraction_agent",
    "restaurant": "restaurant_agent",
    "preparation": "preparation_agent",
    "itinerary": "itinerary_agent",
    "weather": "weather",
    "synthesize": "synthesize",
}

WIDGET_AGENT_NAMES = {
    "hotel_agent",
    "flight_agent",
    "attraction_agent",
    "restaurant_agent",
}


def _pick(source: dict, keys: list[str]) -> dict:
    """Return only present, non-empty fields used by chat widgets."""
    result = {}
    for key in keys:
        value = source.get(key)
        if value is not None and value != "":
            result[key] = value
    return result


def _compact_location(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    coordinates = value.get("coordinates")
    if isinstance(coordinates, list) and len(coordinates) == 2:
        return {"coordinates": coordinates}
    lat = value.get("lat")
    lng = value.get("lng")
    if lat is not None and lng is not None:
        return {"lat": lat, "lng": lng}
    return None


def _compact_db_data(value: object, include_address: bool = False) -> dict:
    if not isinstance(value, dict):
        return {}
    compact = _pick(
        value,
        [
            "imageUrl",
            "thumbnail",
            "reviewRating",
            "reviewCount",
            "category",
        ],
    )
    if include_address and value.get("address"):
        compact["address"] = value["address"]

    location = _compact_location(value.get("location"))
    if location:
        compact["location"] = location
    return compact


def _compact_flight_item(value: object) -> dict | None:
    if not isinstance(value, dict):
        return None
    return _pick(
        value,
        [
            "departure_time",
            "arrival_time",
            "departure_airport_id",
            "arrival_airport_id",
            "flight_number",
            "airline",
            "airline_logo",
            "total_duration_min",
            "stops",
            "price",
            "google_flights_url",
            "direction",
        ],
    )


def _compact_hotel_item(value: object, recommended: bool = False) -> dict:
    if not isinstance(value, dict):
        return {}
    keys = [
        "name",
        "recommend_hotel_name",
        "place_id",
        "placeId",
        "recommend_hotel_placeId",
        "thumbnail",
        "link",
        "totalRate",
        "hotel_class",
        "overallRating",
        "reviews",
        "checkInTime",
        "checkOutTime",
    ]
    compact = _pick(value, keys)
    location = _compact_location(value.get("_location"))
    if location:
        compact["_location"] = location
    if recommended and compact.get("recommend_hotel_placeId") and not compact.get("placeId"):
        compact["placeId"] = compact["recommend_hotel_placeId"]
    return compact


def _compact_attraction_item(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    compact = _pick(
        value,
        [
            "name",
            "place_id",
            "placeId",
            "must_visit",
            "notes",
            "rating",
            "user_ratings_total",
            "estimated_entrance_fee",
        ],
    )
    includes = value.get("includes")
    if isinstance(includes, list):
        compact["includes"] = [
            {"name": item.get("name")}
            for item in includes
            if isinstance(item, dict) and item.get("name")
        ]
    db_data = _compact_db_data(value.get("db_data"))
    if db_data:
        compact["db_data"] = db_data
    location = _compact_location(value.get("_location"))
    if location:
        compact["_location"] = location
    return compact


def _compact_restaurant_item(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    compact = _pick(
        value,
        [
            "day",
            "meal_type",
            "name",
            "place_id",
            "placeId",
            "rating",
            "user_ratings_total",
            "price_level",
            "note",
            "justification",
            "estimated_cost_total",
        ],
    )
    db_data = _compact_db_data(value.get("db_data"), include_address=True)
    if db_data:
        compact["db_data"] = db_data
    location = _compact_location(value.get("_location"))
    if location:
        compact["_location"] = location
    return compact


def _curate_widget_agent_data(agent_name: str, agent_data: object) -> dict | None:
    """Keep only fields consumed by the React chat widgets and map markers."""
    if agent_name not in WIDGET_AGENT_NAMES or not isinstance(agent_data, dict):
        return None

    if agent_name == "flight_agent":
        curated = _pick(
            agent_data,
            [
                "type",
                "totalPrice",
                "google_flights_url",
                "passengers",
                "outbound_date",
                "return_date",
            ],
        )
        outbound = _compact_flight_item(agent_data.get("recommend_outbound_flight"))
        if outbound:
            curated["recommend_outbound_flight"] = outbound
        return_flight = _compact_flight_item(agent_data.get("recommend_return_flight"))
        if return_flight:
            curated["recommend_return_flight"] = return_flight
        alternatives = [
            item
            for item in (
                _compact_flight_item(alt)
                for alt in agent_data.get("alternatives", [])
            )
            if item
        ]
        if alternatives:
            curated["alternatives"] = alternatives
        return curated if curated else None

    if agent_name == "hotel_agent":
        segments = []
        for segment in agent_data.get("segments", []):
            if not isinstance(segment, dict):
                continue
            compact_segment = _compact_hotel_item(segment, recommended=True)
            alternatives = [
                item
                for item in (
                    _compact_hotel_item(alt)
                    for alt in segment.get("alternatives", [])
                )
                if item
            ]
            if alternatives:
                compact_segment["alternatives"] = alternatives
            if compact_segment:
                segments.append(compact_segment)
        return {"segments": segments} if segments else None

    if agent_name == "attraction_agent":
        segments = []
        for segment in agent_data.get("segments", []):
            if not isinstance(segment, dict):
                continue
            attractions = [
                item
                for item in (
                    _compact_attraction_item(attr)
                    for attr in segment.get("attractions", [])
                )
                if item
            ]
            if attractions:
                segments.append({
                    "segment_name": segment.get("segment_name"),
                    "attractions": attractions,
                })
        return {"segments": segments} if segments else None

    if agent_name == "restaurant_agent":
        meals = []
        for meal in agent_data.get("meals", []):
            compact_meal = _compact_restaurant_item(meal)
            if not compact_meal:
                continue
            alternatives = []
            if isinstance(meal, dict):
                for alt in meal.get("alternatives", []):
                    if isinstance(alt, str):
                        alternatives.append(alt)
                    else:
                        compact_alt = _compact_restaurant_item(alt)
                        if compact_alt:
                            alternatives.append(compact_alt)
            if alternatives:
                compact_meal["alternatives"] = alternatives
            meals.append(compact_meal)
        return {"meals": meals} if meals else None

    return None


class AgentStreamRequest(BaseModel):
    """Request body for the agent stream endpoint."""
    conversation_id: str
    message: str


def format_sse(event: AgentEvent) -> str:
    """Format an AgentEvent as an SSE data line."""
    return f"data: {json.dumps(event.to_sse_dict())}\n\n"


@router.post("/api/agent/stream")
async def stream_agent(request_body: AgentStreamRequest, request: Request):
    """
    HTTP POST endpoint that returns an SSE stream of agent events.

    Protocol:
    1. Client sends POST with JSON: {"conversation_id": "...", "message": "..."}
    2. Server responds with SSE stream (Content-Type: text/event-stream)
    3. Server streams AgentEvent JSON objects during graph execution
    4. Server sends workflow_complete event when done
    5. Stream closes automatically after workflow completes
    """
    conversation_id = request_body.conversation_id
    user_message = request_body.message

    logger.info(
        f"📨 SSE stream request: conversation_id={conversation_id}, "
        f"message={user_message[:200] if len(user_message) > 200 else user_message}"
    )

    if not user_message.strip():
        async def error_stream():
            yield format_sse(AgentEvent(
                event_type=EventType.ERROR,
                error_message="Empty message received",
            ))
        return StreamingResponse(
            error_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def event_generator():
        # LangGraph config with PostgresSaver thread_id
        config = {
            "configurable": {
                "thread_id": conversation_id,
            }
        }

        # Check if PostgresSaver has state for this thread
        try:
            existing_state = await agent_graph.compiled_graph.aget_state(config)
            has_existing = existing_state and existing_state.values and "conversation_id" in existing_state.values
        except Exception:
            has_existing = False

        if has_existing:
            logger.info(f"✅ Checkpoint has existing state for thread {conversation_id}")
        else:
            logger.info(f"📚 No existing state for thread {conversation_id}")

        # Prepare graph input
        if has_existing:
            # Checkpoint exists → minimal input, preserve persistent state
            graph_input = {
                "user_message": user_message,
                # Reset per-turn output fields (empty dict triggers reducer to wipe)
                "agent_outputs": {},
                "final_response": "",
                "structured_output": {},
                "constraint_overrides": {},
            }
        else:
            # First message → provide all fields with defaults
            graph_input = {
                "conversation_id": conversation_id,
                "user_message": user_message,
                "agent_outputs": {},
                "current_plan": {},
                "constraint_overrides": {},
                "macro_plan": {},
                "final_response": "",
                "structured_output": {},
                "metadata": {},
            }

        logger.info(f"🚀 Starting LangGraph workflow for conversation {conversation_id}")

        # State for tracking streaming
        active_agents: set[str] = set()
        current_node: str | None = None
        final_response = ""
        streamed_chunks: list[str] = []
        structured_output: dict = {}
        current_plan_snapshot: dict = {}
        user_intent: str = ""

        try:
            async for event in agent_graph.compiled_graph.astream_events(
                graph_input, config=config, version="v2"
            ):
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"🔌 Client disconnected during stream: {conversation_id}")
                    return

                event_kind = event.get("event", "")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                # --- Node (Agent) Start ---
                if event_kind == "on_chain_start" and event_name in NODE_TO_AGENT:
                    agent_name = NODE_TO_AGENT[event_name]
                    current_node = agent_name
                    if agent_name not in active_agents:
                        active_agents.add(agent_name)
                        logger.info(f"▶️  Agent started: {agent_name}")
                        yield format_sse(AgentEvent(
                            event_type=EventType.AGENT_START,
                            agent_name=agent_name,
                        ))

                # --- Node (Agent) End ---
                elif event_kind == "on_chain_end" and event_name in NODE_TO_AGENT:
                    agent_name = NODE_TO_AGENT[event_name]
                    output = event_data.get("output", {})

                    output_summary = None
                    if isinstance(output, dict):
                        current_tool = output.get("current_tool", "")

                        # Send tool events if a tool was used
                        if current_tool:
                            yield format_sse(AgentEvent(
                                event_type=EventType.TOOL_START,
                                agent_name=agent_name,
                                tool_name=current_tool,
                            ))
                            yield format_sse(AgentEvent(
                                event_type=EventType.TOOL_END,
                                agent_name=agent_name,
                                tool_name=current_tool,
                                tool_output={"status": "completed"},
                            ))

                        # Capture final_response from any node
                        final_resp = output.get("final_response", "")
                        if final_resp:
                            final_response = final_resp

                        # Capture structured output
                        struct_out = output.get("structured_output", {})
                        if struct_out:
                            structured_output = struct_out

                        # Capture current_plan for suggestions
                        cp = output.get("current_plan")
                        if cp:
                            current_plan_snapshot = cp

                        # Capture intent from intent_output
                        intent_out = output.get("intent_output")
                        if intent_out and isinstance(intent_out, dict):
                            ri = intent_out.get("intent")
                            if ri:
                                user_intent = ri

                        # Get output summary
                        agent_outputs = output.get("agent_outputs", {})
                        if agent_name in agent_outputs:
                            agent_data = agent_outputs[agent_name]
                            if isinstance(agent_data, dict):
                                output_summary = agent_data.get("summary",
                                    agent_data.get("status",
                                    agent_data.get("search_summary", "")))

                                # Emit only the compact data needed by chat widgets.
                                widget_data = _curate_widget_agent_data(agent_name, agent_data)
                                if widget_data:
                                    yield format_sse(AgentEvent(
                                        event_type=EventType.STRUCTURED_DATA,
                                        agent_name=agent_name,
                                        structured_data=widget_data,
                                    ))

                    logger.info(f"⏹️  Agent ended: {agent_name}")
                    yield format_sse(AgentEvent(
                        event_type=EventType.AGENT_END,
                        agent_name=agent_name,
                        output_summary=output_summary,
                    ))
                    active_agents.discard(agent_name)

                # --- Real LLM Token Streaming ---
                elif event_kind == "on_chat_model_stream":
                    chunk_content = ""
                    chunk_data = event_data.get("chunk", None)
                    if chunk_data and hasattr(chunk_data, "content"):
                        raw_content = chunk_data.content
                        
                        # Handle different LLM provider output formats
                        if isinstance(raw_content, str):
                            chunk_content = raw_content
                        elif isinstance(raw_content, list):
                            # e.g. [{"type": "text", "text": "hello"}]
                            text_parts = []
                            for part in raw_content:
                                if isinstance(part, dict) and "text" in part:
                                    text_parts.append(part["text"])
                                elif isinstance(part, str):
                                    text_parts.append(part)
                            chunk_content = "".join(text_parts)
                        else:
                            chunk_content = str(raw_content)

                    if chunk_content:
                        streamed_chunks.append(chunk_content)
                        agent_for_chunk = current_node or "synthesize"
                        yield format_sse(AgentEvent(
                            event_type=EventType.TEXT_CHUNK,
                            agent_name=agent_for_chunk,
                            content=chunk_content,
                        ))

            # Use streamed content as final response if available
            if streamed_chunks and not final_response:
                final_response = "".join(streamed_chunks)

            # Send structured data if available
            if structured_output:
                yield format_sse(AgentEvent(
                    event_type=EventType.STRUCTURED_DATA,
                    structured_data=structured_output,
                ))

            # Workflow complete
            logger.info(f"✅ Workflow completed for conversation {conversation_id}")

            # Build suggestions from current_plan
            suggestions = []
            if current_plan_snapshot:
                suggestions = current_plan_snapshot.get("last_suggestions", [])

            yield format_sse(AgentEvent(
                event_type=EventType.WORKFLOW_COMPLETE,
                final_response=final_response,
                structured_data={
                    "intent": user_intent,
                    "suggestions": suggestions,
                } if (user_intent or suggestions) else None,
            ))

        except Exception as e:
            logger.error(f"❌ Workflow error: {e}", exc_info=True)
            yield format_sse(AgentEvent(
                event_type=EventType.ERROR,
                error_message=str(e),
            ))

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
