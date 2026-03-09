using dotnet.Enums;

namespace dotnet.Entites
{
    public class Message : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid ConversationId { get; set; }
        public string Content { get; set; } = string.Empty;
        public MessageRole MessageRole { get; set; } = MessageRole.User;

        public Conversation Conversation { get; set; }
    }
}
