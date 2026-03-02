namespace dotnet.Dtos.GoogleCalendar
{
    public class SyncGoogleCalendarResponse
    {
        public DateTimeOffset SyncedAt { get; set; }
        public int CreatedCount { get; set; }
        public int UpdatedCount { get; set; }
        public int DeletedCount { get; set; }
        public List<EventMapping> EventMappings { get; set; } = new();
    }

    public class EventMapping
    {
        public Guid ItineraryItemId { get; set; }
        public string GoogleCalendarEventId { get; set; } = string.Empty;
    }
}
