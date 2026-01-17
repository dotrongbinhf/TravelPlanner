namespace dotnet.Domains
{
    public class Note : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public string Title { get; set; } = string.Empty;
        public string Content { get; set; } = string.Empty;
        public int Order { get; set; }

        public Plan Plan { get; set; }
    }
}
