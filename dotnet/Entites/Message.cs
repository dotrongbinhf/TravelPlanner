using dotnet.Enums;

namespace dotnet.Entites
{
    public class Message : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid ConversationId { get; set; }
        public string Content { get; set; } = string.Empty;
        public MessageRole MessageRole { get; set; } = MessageRole.User;

        /// <summary>
        /// JSON string containing the AI-generated plan data (apply_data).
        /// Only present on Assistant messages that contain a travel plan.
        /// </summary>
        public string? GeneratedPlanData { get; set; }

        /// <summary>
        /// Timestamp when the user applied this generated plan to their trip.
        /// Null if the plan has not been applied yet.
        /// </summary>
        public DateTimeOffset? ApplyGeneratedPlanAt { get; set; }

        public Conversation Conversation { get; set; }
    }
}
