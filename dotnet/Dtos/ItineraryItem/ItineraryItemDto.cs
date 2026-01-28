namespace dotnet.Dtos.ItineraryItem
{
    public class ItineraryItemDto
    {
        public Guid Id { get; set; }
        public Guid ItineraryDayId { get; set; }
        public Guid PlaceId { get; set; }
        public TimeOnly StartTime { get; set; }
        public TimeOnly EndTime { get; set; }
    }
}
