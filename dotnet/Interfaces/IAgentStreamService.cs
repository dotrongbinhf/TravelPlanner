using dotnet.Dtos.AgentEvent;

namespace dotnet.Interfaces
{
    /// <summary>
    /// Service for communicating with the FastAPI LangGraph agent system via HTTP POST + SSE.
    /// Acts as a proxy between .NET and FastAPI: sends message via POST, reads SSE stream back.
    /// Handles only streaming
    /// </summary>
    public interface IAgentStreamService
    {
        /// <summary>
        /// Sends a message to FastAPI and streams back agent events via SSE.
        /// </summary>
        /// <param name="conversationId">The conversation ID (maps to LangGraph thread_id)</param>
        /// <param name="message">The user's message to send to the agent system</param>
        /// <param name="cancellationToken">Cancellation token</param>
        /// <returns>Async enumerable of agent events from the SSE stream</returns>
        IAsyncEnumerable<AgentEventDto> StreamFromFastApiAsync(
            string conversationId,
            string message,
            CancellationToken cancellationToken = default);
    }
}
