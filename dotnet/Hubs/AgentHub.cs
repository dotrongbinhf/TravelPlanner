using System.Text;
using System.Text.Json;
using dotnet.Dtos.AgentEvent;
using dotnet.Dtos.Message;
using dotnet.Enums;
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
    /// Message persistence is handled here (not by the frontend):
    ///   - User message is saved to DB BEFORE forwarding to FastAPI
    ///   - AI response is saved to DB AFTER streaming completes
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
        private static readonly JsonSerializerOptions _jsonOptions = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
        };

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
        /// 1. Saves user message to DB
        /// 2. Streams agent events to frontend while accumulating content
        /// 3. Saves AI response to DB after streaming completes
        /// </summary>
        public async Task SendMessage(string conversationId, string message)
        {
            _logger.LogInformation(
                "AgentHub.SendMessage: conversationId={ConversationId}, message={Message}",
                conversationId,
                message.Length > 100 ? message[..100] + "..." : message);

            try
            {
                // ── Step 1: Save user message to DB ──
                var conversationGuid = Guid.Parse(conversationId);
                await _aiChatService.AddMessage(new CreateMessageDto
                {
                    ConversationId = conversationGuid,
                    Content = message,
                    MessageRole = MessageRole.User
                });
                _logger.LogInformation("💾 User message saved to DB for conversation {ConversationId}", conversationId);

                // ── Step 2: Stream AI response + accumulate for DB persistence ──
                var streamedContent = new StringBuilder();
                string? finalResponse = null;

                // Accumulate structured data from multiple events:
                //   - Per-agent events: { agentName: "hotel_agent", structuredData: {...} }
                //   - Global event: { structuredData: { apply_data: {...}, ... } }
                var structuredDataAccumulator = new Dictionary<string, object>();

                await foreach (var agentEvent in _agentService.StreamAgentResponseAsync(
                    conversationId, message, Context.ConnectionAborted))
                {
                    // Forward event to frontend
                    await Clients.Caller.SendAsync("ReceiveAgentEvent", agentEvent, Context.ConnectionAborted);

                    // Accumulate text chunks
                    if (agentEvent.EventType == "text_chunk" && agentEvent.Content != null)
                    {
                        streamedContent.Append(agentEvent.Content);
                    }

                    // Accumulate structured data (per-agent keyed or global merge)
                    if (agentEvent.EventType == "structured_data" && agentEvent.StructuredData != null)
                    {
                        if (!string.IsNullOrEmpty(agentEvent.AgentName))
                        {
                            // Per-agent structured data: key by agent name
                            structuredDataAccumulator[agentEvent.AgentName] = agentEvent.StructuredData;
                        }
                        else
                        {
                            // Global structured data: merge keys (e.g. apply_data)
                            try
                            {
                                var jsonStr = JsonSerializer.Serialize(agentEvent.StructuredData, _jsonOptions);
                                var dict = JsonSerializer.Deserialize<Dictionary<string, object>>(jsonStr, _jsonOptions);
                                if (dict != null)
                                {
                                    foreach (var kv in dict)
                                    {
                                        structuredDataAccumulator[kv.Key] = kv.Value;
                                    }
                                }
                            }
                            catch
                            {
                                // Best-effort: if parsing fails, store as-is
                                structuredDataAccumulator["_global"] = agentEvent.StructuredData;
                            }
                        }
                    }

                    // Track final response from workflow_complete
                    if (agentEvent.EventType == "workflow_complete")
                    {
                        finalResponse = agentEvent.FinalResponse;
                    }
                }

                // ── Step 3: Save AI response to DB ──
                var aiContent = streamedContent.Length > 0
                    ? streamedContent.ToString()
                    : finalResponse;

                if (!string.IsNullOrEmpty(aiContent))
                {
                    string? generatedPlanData = null;
                    if (structuredDataAccumulator.Count > 0)
                    {
                        try
                        {
                            generatedPlanData = JsonSerializer.Serialize(structuredDataAccumulator, _jsonOptions);
                        }
                        catch (Exception ex)
                        {
                            _logger.LogWarning(ex, "Failed to serialize structured data for DB");
                        }
                    }

                    await _aiChatService.AddMessage(new CreateMessageDto
                    {
                        ConversationId = conversationGuid,
                        Content = aiContent,
                        MessageRole = MessageRole.Chatbot,
                        GeneratedPlanData = generatedPlanData
                    });
                    _logger.LogInformation("💾 AI response saved to DB for conversation {ConversationId}", conversationId);
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
