using dotnet.Enums;

namespace dotnet.Domains
{
    public class Participant : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public PlanRole Role { get; set; }

        public Plan Plan { get; set; }
    }
}
