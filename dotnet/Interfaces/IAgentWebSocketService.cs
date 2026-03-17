using dotnet.Dtos.AgentEvent;
using dotnet.Dtos.Message;

namespace dotnet.Interfaces
{
    /// <summary>
    /// Service for communicating with the FastAPI LangGraph agent system via WebSocket.
    /// Acts as a proxy between .NET (SignalR) and FastAPI (WebSocket).
    /// </summary>
    public interface IAgentWebSocketService
    {
        /// <summary>
        /// Streams agent events from FastAPI by sending a message and yielding back events.
        /// </summary>
        /// <param name="conversationId">The conversation ID (maps to LangGraph thread_id)</param>
        /// <param name="message">The user's message to send to the agent system</param>
        /// <param name="history">Recent conversation messages for context restoration</param>
        /// <param name="cancellationToken">Cancellation token</param>
        /// <returns>Async enumerable of agent events</returns>
        IAsyncEnumerable<AgentEventDto> StreamAgentResponseAsync(
            string conversationId,
            string message,
            IEnumerable<MessageDto>? history = null,
            CancellationToken cancellationToken = default);
    }
}
