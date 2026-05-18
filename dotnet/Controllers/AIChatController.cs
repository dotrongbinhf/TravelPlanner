using System.Text;
using System.Text.Json;
using dotnet.Dtos.AgentEvent;
using dotnet.Dtos.Conversation;
using dotnet.Dtos.Message;
using dotnet.Enums;
using dotnet.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace dotnet.Controllers
{
    [Route("api/aichat")]
    [ApiController]
    [Authorize]
    public class AIChatController : ControllerBase
    {
        private readonly IAIChatService _aiChatService;
        private readonly IAgentStreamService _agentStreamService;
        private readonly ILogger<AIChatController> _logger;
        private static readonly JsonSerializerOptions _jsonOptions = new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        };
        private static readonly HashSet<string> _persistedWidgetAgentNames = new(StringComparer.Ordinal)
        {
            "hotel_agent",
            "flight_agent",
            "attraction_agent",
            "restaurant_agent"
        };

        public AIChatController(
            IAIChatService aiChatService,
            IAgentStreamService agentStreamService,
            ILogger<AIChatController> logger)
        {
            _aiChatService = aiChatService;
            _agentStreamService = agentStreamService;
            _logger = logger;
        }

        [HttpGet("plans/{planId}/conversations")]
        public async Task<IActionResult> GetConversationsByPlanId([FromRoute] Guid planId)
        {
            var result = await _aiChatService.GetConversationsByPlanId(planId);
            return Ok(result);
        }

        [HttpPost("plans/{planId}/conversations")]
        public async Task<IActionResult> CreateConversation([FromRoute] Guid planId, [FromBody] CreateConversationDto createDto)
        {
            createDto.PlanId = planId; // ensure planId matches route
            try
            {
                var result = await _aiChatService.CreateConversation(createDto);
                return Ok(result);
            }
            catch (UnauthorizedAccessException ex)
            {
                return Forbid(ex.Message);
            }
        }

        [HttpPut("conversations/{id}/title")]
        public async Task<IActionResult> UpdateConversationTitle([FromRoute] Guid id, [FromBody] UpdateConversationTitleDto updateDto)
        {
            try
            {
                var result = await _aiChatService.UpdateConversationTitle(id, updateDto);
                return Ok(result);
            }
            catch (KeyNotFoundException)
            {
                return NotFound();
            }
            catch (UnauthorizedAccessException)
            {
                return Forbid();
            }
        }

        [HttpGet("conversations/{id}/messages")]
        public async Task<IActionResult> GetMessages([FromRoute] Guid id)
        {
            try
            {
                var result = await _aiChatService.GetMessagesByConversationId(id);
                return Ok(result);
            }
            catch (UnauthorizedAccessException)
            {
                return Forbid();
            }
        }

        [HttpPost("conversations/{id}/messages")]
        public async Task<IActionResult> AddMessage([FromRoute] Guid id, [FromBody] CreateMessageDto createMessageDto)
        {
            createMessageDto.ConversationId = id; // Ensure matches
            try
            {
                var result = await _aiChatService.AddMessage(createMessageDto);
                return Ok(result);
            }
            catch (KeyNotFoundException)
            {
                return NotFound();
            }
            catch (UnauthorizedAccessException)
            {
                return Forbid();
            }
        }

        /// <summary>
        /// Send a message to the AI agent system and stream back events via SSE.
        /// 
        /// Flow:
        /// 1. Save user message to DB
        /// 2. Forward to FastAPI via HTTP POST
        /// 3. Stream SSE events back to the frontend (text chunks, agent status, structured data)
        /// 4. Save AI response to DB after streaming completes
        /// 
        /// </summary>
        [HttpPost("conversations/{id}/messages/stream")]
        public async Task StreamMessage([FromRoute] Guid id, [FromBody] StreamMessageDto dto)
        {
            _logger.LogInformation(
                "AIChatController.StreamMessage: conversationId={ConversationId}, message={Message}",
                id,
                dto.Content.Length > 100 ? dto.Content[..100] + "..." : dto.Content);

            try
            {
                // ── Step 1: Save user message to DB ──
                await _aiChatService.AddMessage(new CreateMessageDto
                {
                    ConversationId = id,
                    Content = dto.Content,
                    MessageRole = MessageRole.User
                });

                // ── Step 2: Set SSE response headers ──
                Response.ContentType = "text/event-stream";
                Response.Headers.CacheControl = "no-cache";
                Response.Headers.Connection = "keep-alive";
                Response.Headers["X-Accel-Buffering"] = "no";

                // ── Step 3: Stream AI response + accumulate for DB persistence ──
                var streamedContent = new StringBuilder();
                string? finalResponse = null;

                // Accumulate structured data from multiple events:
                //   - Per-agent events: { agentName: "hotel_agent", structuredData: {...} }
                //   - Global event: { structuredData: { apply_data: {...}, ... } }
                var structuredDataAccumulator = new Dictionary<string, object>();

                await foreach (var agentEvent in _agentStreamService.StreamFromFastApiAsync(
                    id.ToString(), dto.Content, HttpContext.RequestAborted))
                {
                    // Forward event to frontend as SSE
                    var eventJson = JsonSerializer.Serialize(agentEvent, _jsonOptions);
                    await Response.WriteAsync($"data: {eventJson}\n\n", HttpContext.RequestAborted);
                    await Response.Body.FlushAsync(HttpContext.RequestAborted);

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
                            // Per-agent structured data: persist only widget payloads.
                            if (_persistedWidgetAgentNames.Contains(agentEvent.AgentName))
                            {
                                structuredDataAccumulator[agentEvent.AgentName] = agentEvent.StructuredData;
                            }
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
                                        if (kv.Key == "apply_data")
                                        {
                                            structuredDataAccumulator[kv.Key] = kv.Value;
                                        }
                                    }
                                }
                            }
                            catch
                            {
                                // if parsing fails, store as-is
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

                // ── Step 4: Save AI response to DB ──
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

                    var savedMessage = await _aiChatService.AddMessage(new CreateMessageDto
                    {
                        ConversationId = id,
                        Content = aiContent,
                        MessageRole = MessageRole.Chatbot,
                        GeneratedPlanData = generatedPlanData
                    });

                    // Send real messageId back to frontend via SSE
                    var savedEvent = new AgentEventDto
                    {
                        EventType = "message_saved",
                        MessageId = savedMessage.Id.ToString(),
                    };
                    var savedJson = JsonSerializer.Serialize(savedEvent, _jsonOptions);
                    await Response.WriteAsync($"data: {savedJson}\n\n");
                    await Response.Body.FlushAsync();
                }
            }
            catch (OperationCanceledException)
            {
                _logger.LogInformation("Stream cancelled for conversation {ConversationId}", id);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in AIChatController.StreamMessage");
                try
                {
                    var errorEvent = new AgentEventDto
                    {
                        EventType = "error",
                        ErrorMessage = $"Server error: {ex.Message}"
                    };
                    var errorJson = JsonSerializer.Serialize(errorEvent, _jsonOptions);
                    await Response.WriteAsync($"data: {errorJson}\n\n");
                    await Response.Body.FlushAsync();
                }
                catch { }
            }
        }

        [HttpDelete("conversations/{id}")]
        public async Task<IActionResult> DeleteConversation([FromRoute] Guid id)
        {
            try
            {
                var result = await _aiChatService.DeleteConversation(id);
                return Ok(result);
            }
            catch (KeyNotFoundException)
            {
                return NotFound();
            }
            catch (UnauthorizedAccessException)
            {
                return Forbid();
            }
        }

        [HttpPatch("messages/{messageId}/applied")]
        public async Task<IActionResult> MarkMessageApplied([FromRoute] Guid messageId)
        {
            try
            {
                var result = await _aiChatService.MarkMessageApplied(messageId);
                return Ok(result);
            }
            catch (KeyNotFoundException)
            {
                return NotFound();
            }
            catch (UnauthorizedAccessException)
            {
                return Forbid();
            }
        }
    }

    /// <summary>
    /// Request body for the SSE stream endpoint.
    /// </summary>
    public class StreamMessageDto
    {
        public string Content { get; set; } = string.Empty;
    }
}

