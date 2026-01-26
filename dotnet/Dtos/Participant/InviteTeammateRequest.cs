using dotnet.Enums;

namespace dotnet.Dtos.Participant
{
    public class InviteTeammateRequest
    {
        public Guid UserId { get; set; }
        public PlanRole Role { get; set; } = PlanRole.Viewer;
    }
}
