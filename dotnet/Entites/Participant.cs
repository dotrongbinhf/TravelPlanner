using dotnet.Enums;

namespace dotnet.Entites
{
    public class Participant : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid UserId { get; set; }
        public Guid PlanId { get; set; }
        public PlanRole Role { get; set; }
        public InvitationStatus Status { get; set; }

        public Plan Plan { get; set; }
        public User User { get; set; }
    }
}
