using dotnet.Dtos.PackingItem;

namespace dotnet.Dtos.PackingList
{
    public class PackingListDto
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public string Name { get; set; } = string.Empty;
        public ICollection<PackingItemDto> PackingItems { get; set; } = new List<PackingItemDto>();

    }
}
