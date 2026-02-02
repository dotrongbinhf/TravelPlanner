using dotnet.Dtos.ItineraryItem;

namespace dotnet.Dtos.ItineraryDay
{
    public class ItineraryDayDto
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public int Order { get; set; }
        public string Title { get; set; } = string.Empty;
        public ICollection<ItineraryItemDto>? ItineraryItems { get; set; }
    }
}
