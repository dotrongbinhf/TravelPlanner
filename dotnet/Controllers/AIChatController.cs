using dotnet.Dtos.Conversation;
using dotnet.Dtos.Message;
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

        public AIChatController(IAIChatService aiChatService)
        {
            _aiChatService = aiChatService;
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
    }
}
