using dotnet.Enums;

namespace dotnet.Dtos.Plan
{
    /// <summary>
    /// Request DTO for the apply-ai endpoint.
    /// Frontend sends only messageId + scope; .NET reads plan data from DB.
    /// </summary>
    public class ApplyAIPlanRequest
    {
        public Guid MessageId { get; set; }
        public ApplyScope ApplyScope { get; set; } = ApplyScope.OnlyChanges;
    }

    // ── Sub-DTOs for deserializing apply_data JSON from DB ──

    public class AIItineraryDay
    {
        public int Order { get; set; }
        public string Title { get; set; } = string.Empty;
        public List<AIItineraryItem> Items { get; set; } = new();
    }

    public class AIItineraryItem
    {
        public string? PlaceId { get; set; }
        public string PlaceName { get; set; } = string.Empty;
        public string Role { get; set; } = string.Empty;
        public List<string>? Roles { get; set; }
        public string StartTime { get; set; } = string.Empty;
        public int Duration { get; set; }
        public string? Note { get; set; }
    }

    public class AIExpenseItem
    {
        public string Category { get; set; } = "Other";
        public string Name { get; set; } = string.Empty;
        public double Amount { get; set; }
    }

    public class AIPackingList
    {
        public string Name { get; set; } = string.Empty;
        public List<string> Items { get; set; } = new();
    }

    public class AINote
    {
        public string Title { get; set; } = string.Empty;
        public string Content { get; set; } = string.Empty;
    }
}
