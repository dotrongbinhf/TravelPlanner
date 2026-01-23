namespace dotnet.Domains
{
    public class ItineraryItem : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public Guid PlaceId { get; set; }
        public DateTime Date { get; set; }
        //public int Order { get; set; }
        public DateTime StartTime { get; set; }
        public DateTime EndTime { get; set; }
        public string? Note { get; set; }

        public Plan Plan { get; set; }
    }
}
