using System;
using System.ComponentModel.DataAnnotations;

namespace dotnet.Dtos.Conversation
{
    public class CreateConversationDto
    {
        [Required]
        public Guid PlanId { get; set; }
        public string? Title { get; set; } 
    }
}
