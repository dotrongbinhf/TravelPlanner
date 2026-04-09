namespace dotnet.Dtos.ItineraryItem
{
    public class UpdateItineraryItemRequest
    {
        public Guid ItineraryDayId { get; set; }
        public string? PlaceId { get; set; }
        public TimeOnly? StartTime { get; set; }
        public TimeSpan? Duration { get; set; }
        public string? Note { get; set; }
    }
}
