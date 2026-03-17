using dotnet.Dtos.AgentEvent;
using dotnet.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.SignalR;

namespace dotnet.Hubs
{
    /// <summary>
    /// SignalR Hub for realtime AI Agent communication.
    /// 
    /// Frontend connects via SignalR, sends messages, and receives streaming agent events.
    /// This hub acts as the bridge: NextJS ↔ SignalR ↔ .NET ↔ WebSocket ↔ FastAPI.
    /// 
    /// Client methods to listen:
    ///   - "ReceiveAgentEvent": receives AgentEventDto for each streaming event
    /// </summary>
    [Authorize]
    public class AgentHub : Hub
    {
        private readonly IAgentWebSocketService _agentService;
        private readonly IAIChatService _aiChatService;
        private readonly ILogger<AgentHub> _logger;

        public AgentHub(
            IAgentWebSocketService agentService,
            IAIChatService aiChatService,
            ILogger<AgentHub> logger)
        {
            _agentService = agentService;
            _aiChatService = aiChatService;
            _logger = logger;
        }

        /// <summary>
        /// Invoked by the frontend to send a message to the AI agent system.
        /// Loads recent conversation history from DB and streams back AgentEventDto objects via "ReceiveAgentEvent".
        /// </summary>
        /// <param name="conversationId">The conversation ID</param>
        /// <param name="message">The user's message</param>
        public async Task SendMessage(string conversationId, string message)
        {
            _logger.LogInformation(
                "AgentHub.SendMessage: conversationId={ConversationId}, message={Message}",
                conversationId,
                message.Length > 100 ? message[..100] + "..." : message);

            try
            {
                // Load recent messages from DB for context restoration after server restart
                var history = await _aiChatService.GetMessagesByConversationId(Guid.Parse(conversationId));
                var recentHistory = history.TakeLast(10).ToList();

                _logger.LogInformation("Loaded {Count} recent messages for conversation {ConversationId}",
                    recentHistory.Count, conversationId);

                await foreach (var agentEvent in _agentService.StreamAgentResponseAsync(
                    conversationId, message, recentHistory, Context.ConnectionAborted))
                {
                    await Clients.Caller.SendAsync("ReceiveAgentEvent", agentEvent, Context.ConnectionAborted);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in AgentHub.SendMessage");
                await Clients.Caller.SendAsync("ReceiveAgentEvent", new AgentEventDto
                {
                    EventType = "error",
                    ErrorMessage = $"Server error: {ex.Message}"
                });
            }
        }

        public override async Task OnConnectedAsync()
        {
            _logger.LogInformation("AgentHub client connected: {ConnectionId}", Context.ConnectionId);
            await base.OnConnectedAsync();
        }

        public override async Task OnDisconnectedAsync(Exception? exception)
        {
            _logger.LogInformation("AgentHub client disconnected: {ConnectionId}", Context.ConnectionId);
            await base.OnDisconnectedAsync(exception);
        }
    }
}
