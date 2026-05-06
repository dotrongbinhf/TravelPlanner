using dotnet.Enums;

namespace dotnet.Dtos.Collaborator
{
    public class CollaboratorDto
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

    public class InviteCollaboratorRequest
    {
        public Guid UserId { get; set; }
        public PlanRole Role { get; set; }
    }

    public class RespondInvitationRequest
    {
        public InvitationStatus Status { get; set; }
    }
}
