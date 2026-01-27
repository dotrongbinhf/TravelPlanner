using dotnet.Enums;

namespace dotnet.Dtos.Participant
{
    public class ParticipantDto
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public Guid PlanId { get; set; }
        public PlanRole Role { get; set; }
        public InvitationStatus Status { get; set; }
        // UserInfo
        public string? Name { get; set; }
        public string? Username { get; set; }
        public string? AvatarUrl { get; set; }
    }
}
