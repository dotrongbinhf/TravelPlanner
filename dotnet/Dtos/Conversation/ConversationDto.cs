using System;

namespace dotnet.Dtos.Conversation
{
    public class ConversationDto
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public string Title { get; set; } = string.Empty;
        public DateTimeOffset CreatedAt { get; set; }
        public DateTimeOffset? UpdatedAt { get; set; }
    }
}
