using System.Net.WebSockets;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;
using System.Threading.Channels;
using dotnet.Dtos.AgentEvent;
using dotnet.Dtos.Message;
using dotnet.Enums;
using dotnet.Interfaces;

namespace dotnet.Services
{
    /// <summary>
    /// WebSocket client that connects to FastAPI LangGraph agent system.
    /// Proxies messages from .NET to FastAPI and streams back agent events.
    /// Uses Channel<T> to bridge async WebSocket reads with IAsyncEnumerable yield.
    /// </summary>
    public class AgentWebSocketService : IAgentWebSocketService
    {
        private readonly IConfiguration _configuration;
        private readonly ILogger<AgentWebSocketService> _logger;
        private readonly JsonSerializerOptions _jsonOptions;

        public AgentWebSocketService(
            IConfiguration configuration,
            ILogger<AgentWebSocketService> logger)
        {
            _configuration = configuration;
            _logger = logger;
            _jsonOptions = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
            };
        }

        public async IAsyncEnumerable<AgentEventDto> StreamAgentResponseAsync(
            string conversationId,
            string message,
            IEnumerable<MessageDto>? history = null,
            [EnumeratorCancellation] CancellationToken cancellationToken = default)
        {
            var channel = Channel.CreateUnbounded<AgentEventDto>();

            // Start the WebSocket reader as a background task
            _ = Task.Run(async () =>
            {
                await ReadFromWebSocketAsync(conversationId, message, history, channel.Writer, cancellationToken);
            }, cancellationToken);

            // Yield events from the channel
            await foreach (var agentEvent in channel.Reader.ReadAllAsync(cancellationToken))
            {
                yield return agentEvent;
            }
        }

        private async Task ReadFromWebSocketAsync(
            string conversationId,
            string message,
            IEnumerable<MessageDto>? history,
            ChannelWriter<AgentEventDto> writer,
            CancellationToken cancellationToken)
        {
            var fastApiUrl = _configuration["FastApiUrl"] ?? "http://localhost:8000";
            var wsUrl = fastApiUrl
                .Replace("https://", "wss://")
                .Replace("http://", "ws://");
            wsUrl = $"{wsUrl}/ws/agent/{conversationId}";

            _logger.LogInformation("Connecting to FastAPI WebSocket: {Url}", wsUrl);

            using var ws = new ClientWebSocket();

            try
            {
                await ws.ConnectAsync(new Uri(wsUrl), cancellationToken);
                _logger.LogInformation("Connected to FastAPI WebSocket for conversation {ConversationId}", conversationId);

                // Build payload with message and optional history
                var payloadObj = new Dictionary<string, object> { ["message"] = message };
                if (history != null && history.Any())
                {
                    payloadObj["history"] = history.Select(m => new
                    {
                        role = m.MessageRole == MessageRole.User ? "user" : "assistant",
                        content = m.Content
                    }).ToList();
                }
                var payload = JsonSerializer.Serialize(payloadObj, _jsonOptions);
                var sendBuffer = Encoding.UTF8.GetBytes(payload);
                await ws.SendAsync(
                    new ArraySegment<byte>(sendBuffer),
                    WebSocketMessageType.Text,
                    true,
                    cancellationToken);

                _logger.LogInformation("Sent message to FastAPI: {Message}", message.Length > 100 ? message[..100] + "..." : message);

                // Receive streaming events
                var receiveBuffer = new byte[4096];
                var messageBuffer = new StringBuilder();

                while (ws.State == WebSocketState.Open && !cancellationToken.IsCancellationRequested)
                {
                    var result = await ws.ReceiveAsync(
                        new ArraySegment<byte>(receiveBuffer),
                        cancellationToken);

                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        _logger.LogInformation("FastAPI WebSocket closed.");
                        break;
                    }

                    if (result.MessageType == WebSocketMessageType.Text)
                    {
                        messageBuffer.Append(Encoding.UTF8.GetString(receiveBuffer, 0, result.Count));

                        if (result.EndOfMessage)
                        {
                            var json = messageBuffer.ToString();
                            messageBuffer.Clear();

                            var agentEvent = ParseAgentEvent(json);
                            if (agentEvent != null)
                            {
                                _logger.LogDebug("Received event: {EventType} from {AgentName}",
                                    agentEvent.EventType, agentEvent.AgentName);
                                await writer.WriteAsync(agentEvent, cancellationToken);

                                // Stop after workflow_complete or error
                                if (agentEvent.EventType == "workflow_complete" ||
                                    agentEvent.EventType == "error")
                                {
                                    break;
                                }
                            }
                        }
                    }
                }
            }
            catch (WebSocketException ex)
            {
                _logger.LogError(ex, "WebSocket error connecting to FastAPI");
                await writer.WriteAsync(new AgentEventDto
                {
                    EventType = "error",
                    ErrorMessage = $"Failed to connect to AI Agent service: {ex.Message}"
                }, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                _logger.LogInformation("Agent stream cancelled");
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unexpected error in agent stream");
                await writer.WriteAsync(new AgentEventDto
                {
                    EventType = "error",
                    ErrorMessage = $"Unexpected error: {ex.Message}"
                }, cancellationToken);
            }
            finally
            {
                writer.Complete();

                if (ws.State == WebSocketState.Open)
                {
                    try
                    {
                        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "Done", CancellationToken.None);
                    }
                    catch { /* best-effort close */ }
                }
            }
        }

        private AgentEventDto? ParseAgentEvent(string json)
        {
            try
            {
                return JsonSerializer.Deserialize<AgentEventDto>(json, _jsonOptions);
            }
            catch (JsonException ex)
            {
                _logger.LogWarning(ex, "Failed to parse agent event JSON: {Json}", json.Length > 200 ? json[..200] : json);
                return null;
            }
        }
    }
}
