using System.ComponentModel.DataAnnotations;

namespace dotnet.Dtos.Conversation
{
    public class UpdateConversationTitleDto
    {
        [Required]
        public string Title { get; set; } = string.Empty;
    }
}
