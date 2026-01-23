namespace dotnet.Dtos.PackingItem
{
    public class UpdatePackingItemRequest
    {
        public string? Name { get; set; } = string.Empty;
        public bool? IsPacked { get; set; }
    }
}
