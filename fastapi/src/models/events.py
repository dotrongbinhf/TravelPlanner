"""
WebSocket streaming event models.

Defines the structured JSON events sent through WebSocket during LangGraph workflow execution.
These events allow the frontend to display realtime agent status, tool usage, text streaming,
and structured plan data.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """Types of streaming events sent via WebSocket."""

    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TEXT_CHUNK = "text_chunk"
    STRUCTURED_DATA = "structured_data"
    DB_COMMANDS = "db_commands"
    PLACE_RESOLVED = "place_resolved"
    WORKFLOW_COMPLETE = "workflow_complete"
    ERROR = "error"


class AgentEvent(BaseModel):
    """
    Structured WebSocket event for realtime streaming.

    Sent to the client during LangGraph workflow execution to provide
    live updates on agent activity, tool usage, text generation,
    and structured plan data.
    """

    event_type: EventType
    agent_name: Optional[str] = None
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict[str, Any]] = None
    tool_output: Optional[dict[str, Any]] = None
    output_summary: Optional[str] = None
    final_response: Optional[str] = None
    structured_data: Optional[dict[str, Any]] = None
    db_commands: Optional[list[dict[str, Any]]] = None
    place_data: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_ws_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict for WebSocket transmission."""
        data = {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
        }
        # Only include non-None fields to keep payloads lean
        if self.agent_name is not None:
            data["agent_name"] = self.agent_name
        if self.content is not None:
            data["content"] = self.content
        if self.tool_name is not None:
            data["tool_name"] = self.tool_name
        if self.tool_input is not None:
            data["tool_input"] = self.tool_input
        if self.tool_output is not None:
            data["tool_output"] = self.tool_output
        if self.output_summary is not None:
            data["output_summary"] = self.output_summary
        if self.final_response is not None:
            data["final_response"] = self.final_response
        if self.structured_data is not None:
            data["structured_data"] = self.structured_data
        if self.db_commands is not None:
            data["db_commands"] = self.db_commands
        if self.place_data is not None:
            data["place_data"] = self.place_data
        if self.error_message is not None:
            data["error_message"] = self.error_message
        return data
