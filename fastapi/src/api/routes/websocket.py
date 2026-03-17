"""
WebSocket endpoint for the LangGraph multi-agent system.

Provides realtime streaming of agent events to connected clients (typically .NET backend).
Uses `astream_events` with version="v2" to capture granular LangGraph events and maps
them to structured AgentEvent objects sent as JSON through the WebSocket.

Key event mappings:
- on_chain_start/end (node names) → agent_start/agent_end
- on_chat_model_stream → text_chunk (realtime LLM token streaming)
- Tool usage from node outputs → tool_start/tool_end

Endpoint: ws://localhost:8000/ws/agent/{conversation_id}
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.graph import compiled_graph
from src.models.events import AgentEvent, EventType

logger = logging.getLogger(__name__)

router = APIRouter()

# Track which LangGraph node names map to our agent names
NODE_TO_AGENT = {
    "planner": "planner",
    "researcher": "researcher",
    "dotnet_integration": "dotnet_integration",
    "response": "response",
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
    2. Client sends JSON: {"message": "user message text"}
    3. Server streams AgentEvent JSON objects during graph execution
    4. Server sends workflow_complete event when done
    5. Connection stays open for additional messages (multi-turn)

    The conversation_id maps to MemorySaver's thread_id for automatic
    conversation memory management across multiple messages.
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
            except json.JSONDecodeError:
                user_message = raw_data
                history = []

            if not user_message.strip():
                await send_event(websocket, AgentEvent(
                    event_type=EventType.ERROR,
                    error_message="Empty message received",
                ))
                continue

            # LangGraph config with MemorySaver thread_id
            config = {
                "configurable": {
                    "thread_id": conversation_id,
                }
            }

            # Check if MemorySaver already has state for this thread
            # If not (e.g. after server restart), inject history from DB
            history_messages = []
            try:
                existing_state = compiled_graph.get_state(config)
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
                logger.info(f"✅ MemorySaver has existing state for thread {conversation_id}, skipping history injection")

            # Prepare graph input
            graph_input = {
                "conversation_id": conversation_id,
                "messages": history_messages + [HumanMessage(content=user_message)],
                "current_agent": "",
                "current_tool": "",
                "agent_outputs": {},
                "dotnet_api_response": {},
                "final_response": "",
                "plan_needs_research": False,
                "plan_needs_details": False,
                "metadata": {},
            }

            logger.info(f"🚀 Starting LangGraph workflow for conversation {conversation_id}")

            # State for tracking streaming
            active_agents: set[str] = set()
            current_node: str | None = None  # Track which node is currently running
            final_response = ""
            streamed_chunks: list[str] = []  # Collect streamed text for final_response

            try:
                async for event in compiled_graph.astream_events(
                    graph_input, config=config, version="v2"
                ):
                    event_kind = event.get("event", "")
                    event_name = event.get("name", "")
                    event_data = event.get("data", {})
                    event_tags = event.get("tags", [])

                    # --- Node (Agent) Start ---
                    if event_kind == "on_chain_start" and event_name in NODE_TO_AGENT:
                        agent_name = NODE_TO_AGENT[event_name]
                        current_node = agent_name  # Track current node for LLM stream mapping
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

                            # Capture final_response from response node
                            final_resp = output.get("final_response", "")
                            if agent_name == "response" and final_resp:
                                final_response = final_resp

                            # Get output summary from agent_outputs
                            agent_outputs = output.get("agent_outputs", {})
                            if agent_name in agent_outputs:
                                agent_data = agent_outputs[agent_name]
                                output_summary = agent_data.get("summary", agent_data.get("plan_summary", ""))

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
                            chunk_content = chunk_data.content

                        if chunk_content:
                            streamed_chunks.append(chunk_content)
                            # Map to the current active node
                            # In response_node, this gives us realtime text
                            agent_for_chunk = current_node or "response"
                            await send_event(websocket, AgentEvent(
                                event_type=EventType.TEXT_CHUNK,
                                agent_name=agent_for_chunk,
                                content=chunk_content,
                            ))

                # Use streamed content as final response if we got stream tokens
                if streamed_chunks and not final_response:
                    final_response = "".join(streamed_chunks)

                # Workflow complete
                logger.info(f"✅ Workflow completed for conversation {conversation_id}")
                await send_event(websocket, AgentEvent(
                    event_type=EventType.WORKFLOW_COMPLETE,
                    final_response=final_response,
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
