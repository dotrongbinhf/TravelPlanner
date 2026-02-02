namespace dotnet.Dtos.ItineraryItem
{
    public class CreateItineraryItemRequest
    {
        public string PlaceId { get; set; }
        public TimeOnly StartTime { get; set; }
        public TimeOnly EndTime { get; set; }
    }
}
