namespace dotnet.Entites
{
    public class ItineraryItem : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid ItineraryDayId { get; set; }
        public string PlaceId { get; set; }
        public TimeOnly? StartTime { get; set; }
        public TimeOnly? EndTime { get; set; }
        // public string? Note { get; set; }

        public ItineraryDay ItineraryDay { get; set; }
    }
}
