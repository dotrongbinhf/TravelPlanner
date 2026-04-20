"""
WebSocket endpoint for the LangGraph multi-agent system.

Provides realtime streaming of agent events to connected clients.
Uses `astream_events` with version="v2" to capture granular LangGraph events
and maps them to structured AgentEvent objects sent as JSON through WebSocket.

Endpoint: ws://localhost:8000/ws/agent/{conversation_id}
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

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


async def send_event(websocket: WebSocket, event: AgentEvent):
    """Send an AgentEvent as JSON through the WebSocket."""
    try:
        await websocket.send_json(event.to_ws_dict())
    except Exception as e:
        logger.error(f"Failed to send WebSocket event: {e}")




@router.websocket("/ws/agent/{conversation_id}")
async def agent_websocket(websocket: WebSocket, conversation_id: str):
    """
    WebSocket endpoint for streaming LangGraph agent events.

    Protocol:
    1. Client connects to ws://host:port/ws/agent/{conversation_id}
    2. Client sends JSON: {"message": "user message text", "plan_id": "optional"}
    3. Server streams AgentEvent JSON objects during graph execution
    4. Server sends workflow_complete event when done
    5. Connection stays open for additional messages (multi-turn)
    """
    await websocket.accept()
    logger.info(f"🔌 WebSocket connected: conversation_id={conversation_id}")

    try:
        while True:
            # Wait for client message
            raw_data = await websocket.receive_text()
            logger.info(f"📨 Received message on conversation {conversation_id}: {raw_data[:200]}")

            try:
                data = json.loads(raw_data)
                user_message = data.get("message", "")
                history = data.get("history", [])
                plan_id = data.get("plan_id", "")
            except json.JSONDecodeError:
                user_message = raw_data
                history = []
                plan_id = ""

            if not user_message.strip():
                await send_event(websocket, AgentEvent(
                    event_type=EventType.ERROR,
                    error_message="Empty message received",
                ))
                continue

            # LangGraph config with PostgresSaver thread_id
            config = {
                "configurable": {
                    "thread_id": conversation_id,
                }
            }

            # Check if PostgresSaver has state for this thread
            # With PostgresSaver, state persists across server restarts
            history_messages = []
            try:
                existing_state = await agent_graph.compiled_graph.aget_state(config)
                has_existing = existing_state and existing_state.values and existing_state.values.get("messages")
            except Exception:
                has_existing = False

            if not has_existing and history:
                logger.info(f"📚 No existing state for thread {conversation_id}, injecting {len(history)} history messages")
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if not content:
                        continue
                    if role == "user":
                        history_messages.append(HumanMessage(content=content))
                    else:
                        history_messages.append(AIMessage(content=content))
            elif has_existing:
                logger.info(f"✅ Checkpoint has existing state for thread {conversation_id}")


            # Deduplicate: if history already ends with same user message, don't add again
            if history_messages and isinstance(history_messages[-1], HumanMessage) and history_messages[-1].content.strip() == user_message.strip():
                logger.info(f"\u26a0\ufe0f Deduplicating: last history message matches current user message")
                input_messages = history_messages
            else:
                input_messages = history_messages + [HumanMessage(content=user_message)]

            # Prepare graph input
            # IMPORTANT: Only include fields that need to be SET or RESET each turn.
            # Persistent fields (current_plan, user_context, macro_plan, metadata)
            # are preserved from the PostgresSaver checkpoint automatically.
            if has_existing:
                # Checkpoint exists → minimal input, preserve persistent state
                graph_input = {
                    "messages": input_messages,
                    # Reset per-turn output fields (clear_all flag triggers reducer to wipe)
                    "agent_outputs": {"clear_all": True},
                    "final_response": "",
                    "structured_output": {},
                    "constraint_overrides": {},
                }
            else:
                # First message → provide all fields with defaults
                graph_input = {
                    "conversation_id": conversation_id,
                    "plan_id": plan_id,
                    "messages": input_messages,
                    "user_context": {},
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
            routed_intent: str = ""

            try:
                async for event in agent_graph.compiled_graph.astream_events(
                    graph_input, config=config, version="v2"
                ):
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
                            await send_event(websocket, AgentEvent(
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
                                await send_event(websocket, AgentEvent(
                                    event_type=EventType.TOOL_START,
                                    agent_name=agent_name,
                                    tool_name=current_tool,
                                ))
                                await send_event(websocket, AgentEvent(
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

                            # Capture routed_intent
                            ri = output.get("routed_intent")
                            if ri:
                                routed_intent = ri

                            # Get output summary
                            agent_outputs = output.get("agent_outputs", {})
                            if agent_name in agent_outputs:
                                agent_data = agent_outputs[agent_name]
                                if isinstance(agent_data, dict):
                                    output_summary = agent_data.get("summary",
                                        agent_data.get("status",
                                        agent_data.get("search_summary", "")))

                                    # --- Emit raw Agent Data for Generative UI injection ---
                                    await send_event(websocket, AgentEvent(
                                        event_type=EventType.STRUCTURED_DATA,
                                        agent_name=agent_name,
                                        structured_data=agent_data,
                                    ))

                        logger.info(f"⏹️  Agent ended: {agent_name}")
                        await send_event(websocket, AgentEvent(
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
                            await send_event(websocket, AgentEvent(
                                event_type=EventType.TEXT_CHUNK,
                                agent_name=agent_for_chunk,
                                content=chunk_content,
                            ))

                # Use streamed content as final response if available
                if streamed_chunks and not final_response:
                    final_response = "".join(streamed_chunks)

                # Send structured data if available
                if structured_output:
                    await send_event(websocket, AgentEvent(
                        event_type=EventType.STRUCTURED_DATA,
                        structured_data=structured_output,
                    ))

                # Workflow complete
                logger.info(f"✅ Workflow completed for conversation {conversation_id}")

                # Build suggestions from current_plan
                suggestions = []
                if current_plan_snapshot:
                    suggestions = current_plan_snapshot.get("last_suggestions", [])

                await send_event(websocket, AgentEvent(
                    event_type=EventType.WORKFLOW_COMPLETE,
                    final_response=final_response,
                    structured_data={
                        "intent": routed_intent,
                        "suggestions": suggestions,
                    } if (routed_intent or suggestions) else None,
                ))

            except Exception as e:
                logger.error(f"❌ Workflow error: {e}", exc_info=True)
                await send_event(websocket, AgentEvent(
                    event_type=EventType.ERROR,
                    error_message=str(e),
                ))

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: conversation_id={conversation_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}", exc_info=True)
