namespace dotnet.Entites
{
    public class ItineraryItem : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid ItineraryDayId { get; set; }
        public string PlaceId { get; set; }
        public TimeOnly StartTime { get; set; }
        // Duration to handle cross days activity
        public TimeSpan Duration { get; set; }

        // Google Calendar sync
        public string? GoogleCalendarEventId { get; set; }
        public bool IsDeleted { get; set; } = false;

        // public string? Note { get; set; }

        public ItineraryDay ItineraryDay { get; set; }
    }
}
