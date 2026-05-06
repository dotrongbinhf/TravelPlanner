using System.IO;
using System.Net.Http;
using System.Runtime.CompilerServices;
using System.Text;
using System.Text.Json;
using dotnet.Dtos.AgentEvent;
using dotnet.Interfaces;

namespace dotnet.Services
{
    /// <summary>
    /// SSE client that connects to FastAPI LangGraph agent system via HTTP POST.
    /// Sends the user message in the POST body and reads back SSE (Server-Sent Events) stream.
    /// 
    /// This service only handles streaming — message persistence is managed by the controller.
    /// </summary>
    public class AgentStreamService : IAgentStreamService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly IConfiguration _configuration;
        private readonly ILogger<AgentStreamService> _logger;
        private readonly JsonSerializerOptions _jsonOptions;

        public AgentStreamService(
            IHttpClientFactory httpClientFactory,
            IConfiguration configuration,
            ILogger<AgentStreamService> logger)
        {
            _httpClientFactory = httpClientFactory;
            _configuration = configuration;
            _logger = logger;
            _jsonOptions = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
            };
        }

        public async IAsyncEnumerable<AgentEventDto> StreamFromFastApiAsync(
            string conversationId,
            string message,
            [EnumeratorCancellation] CancellationToken cancellationToken = default)
        {
            var fastApiUrl = _configuration["FastApiUrl"] ?? "http://localhost:8000";
            var streamUrl = $"{fastApiUrl}/api/agent/stream";

            _logger.LogInformation("Sending POST to FastAPI SSE endpoint: {Url}", streamUrl);

            var httpClient = _httpClientFactory.CreateClient("FastApiStream");

            // Build request
            var payloadObj = new Dictionary<string, object>
            {
                ["conversation_id"] = conversationId,
                ["message"] = message
            };
            var payload = JsonSerializer.Serialize(payloadObj, _jsonOptions);

            var request = new HttpRequestMessage(HttpMethod.Post, streamUrl)
            {
                Content = new StringContent(payload, Encoding.UTF8, "application/json")
            };

            HttpResponseMessage? response = null;
            Stream? stream = null;
            StreamReader? reader = null;

            try
            {
                // Send request with ResponseHeadersRead to start reading stream immediately
                response = await httpClient.SendAsync(
                    request,
                    HttpCompletionOption.ResponseHeadersRead,
                    cancellationToken);

                response.EnsureSuccessStatusCode();

                _logger.LogInformation("Connected to FastAPI SSE stream for conversation {ConversationId}", conversationId);

                stream = await response.Content.ReadAsStreamAsync(cancellationToken);
                reader = new StreamReader(stream);

                while (!reader.EndOfStream && !cancellationToken.IsCancellationRequested)
                {
                    var line = await reader.ReadLineAsync(cancellationToken);

                    if (string.IsNullOrEmpty(line))
                        continue;

                    // SSE format: "data: {...json...}"
                    if (line.StartsWith("data: "))
                    {
                        var json = line[6..]; // Remove "data: " prefix
                        var agentEvent = ParseAgentEvent(json);

                        if (agentEvent != null)
                        {
                            _logger.LogDebug("Received SSE event: {EventType} from {AgentName}",
                                agentEvent.EventType, agentEvent.AgentName);

                            yield return agentEvent;

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
            finally
            {
                reader?.Dispose();
                stream?.Dispose();
                response?.Dispose();
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
                _logger.LogWarning(ex, "Failed to parse SSE event JSON: {Json}", json.Length > 200 ? json[..200] : json);
                return null;
            }
        }
    }
}
