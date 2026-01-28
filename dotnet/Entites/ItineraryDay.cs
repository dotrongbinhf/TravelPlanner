namespace dotnet.Entites
{
    public class ItineraryDay : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public int Order { get; set; }
        public string Title { get; set; } = string.Empty;

        public Plan Plan { get; set; }
        public ICollection<ItineraryItem> ItineraryItems { get; set; } = new List<ItineraryItem>();
    }
}
