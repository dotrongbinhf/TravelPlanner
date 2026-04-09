namespace dotnet.Entites
{
    public class ItineraryItem : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid ItineraryDayId { get; set; }
        public string? PlaceId { get; set; }
        public TimeOnly? StartTime { get; set; }
        // Duration to handle cross days activity
        public TimeSpan? Duration { get; set; }

        // AI-generated or user-added note (e.g. "Check-in & rest", "Explore Old Quarter")
        public string? Note { get; set; }

        // Google Calendar sync
        public string? GoogleCalendarEventId { get; set; }
        public bool IsDeleted { get; set; } = false;

        public ItineraryDay ItineraryDay { get; set; }
    }
}
