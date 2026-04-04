namespace dotnet.Dtos.AgentEvent
{
    /// <summary>
    /// Represents a streaming event from the LangGraph multi-agent system.
    /// Sent from .NET to React frontend via SignalR.
    /// </summary>
    public class AgentEventDto
    {
        /// <summary>
        /// Type of event: agent_start, agent_end, tool_start, tool_end, text_chunk, workflow_complete, error
        /// </summary>
        public string EventType { get; set; } = string.Empty;

        /// <summary>
        /// Name of the agent that generated this event (e.g., "planner", "researcher")
        /// </summary>
        public string? AgentName { get; set; }

        /// <summary>
        /// Text content for text_chunk events (partial streaming text)
        /// </summary>
        public string? Content { get; set; }

        /// <summary>
        /// Name of the tool being used (for tool_start/tool_end events)
        /// </summary>
        public string? ToolName { get; set; }

        /// <summary>
        /// Tool input data (for tool_start events)
        /// </summary>
        public object? ToolInput { get; set; }

        /// <summary>
        /// Tool output data (for tool_end events)
        /// </summary>
        public object? ToolOutput { get; set; }

        /// <summary>
        /// Summary of agent output (for agent_end events)
        /// </summary>
        public string? OutputSummary { get; set; }

        /// <summary>
        /// Final assembled response (for workflow_complete events)
        /// </summary>
        public string? FinalResponse { get; set; }

        /// <summary>
        /// Error message (for error events)
        /// </summary>
        public string? ErrorMessage { get; set; }

        /// <summary>
        /// Structured data payload from the AI pipeline (for structured_data events).
        /// Contains apply_data with normalized plan data for the Apply AI Plan feature.
        /// </summary>
        public object? StructuredData { get; set; }

        /// <summary>
        /// Timestamp of the event
        /// </summary>
        public string? Timestamp { get; set; }
    }
}
