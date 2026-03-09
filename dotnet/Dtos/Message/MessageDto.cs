using System;
using dotnet.Enums;

namespace dotnet.Dtos.Message
{
    public class MessageDto
    {
        public Guid Id { get; set; }
        public Guid ConversationId { get; set; }
        public string Content { get; set; } = string.Empty;
        public MessageRole MessageRole { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
    }
}
