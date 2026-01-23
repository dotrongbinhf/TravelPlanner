namespace dotnet.Dtos.PackingItem
{
    public class PackingItemDto
    {
        public Guid Id { get; set; }
        public Guid PackingListId { get; set; }
        public string Name { get; set; } = string.Empty;
        public bool IsPacked { get; set; }
    }
}
