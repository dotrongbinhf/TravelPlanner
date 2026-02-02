namespace dotnet.Dtos.ItineraryItem
{
    public class UpdateItineraryItemRequest
    {
        public Guid ItineraryDayId { get; set; }
        public TimeOnly StartTime { get; set; }
        public TimeOnly EndTime { get; set; }
    }
}
