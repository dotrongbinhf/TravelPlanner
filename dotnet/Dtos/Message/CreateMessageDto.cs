using System;
using System.ComponentModel.DataAnnotations;
using dotnet.Enums;

namespace dotnet.Dtos.Message
{
    public class CreateMessageDto
    {
        [Required]
        public Guid ConversationId { get; set; }
        [Required]
        public string Content { get; set; } = string.Empty;
        public MessageRole MessageRole { get; set; } = MessageRole.User;
        public string? GeneratedPlanData { get; set; }
    }
}
