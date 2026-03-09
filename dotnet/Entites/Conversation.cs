namespace dotnet.Entites
{
    public class Conversation : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public string Title { get; set; } = string.Empty;

        public Plan Plan { get; set; }
        public ICollection<Message> Messages { get; set; } = new List<Message>();
    }
}
