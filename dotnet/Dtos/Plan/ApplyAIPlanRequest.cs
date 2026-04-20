using dotnet.Enums;

namespace dotnet.Dtos.Plan
{
    public class ApplyAIPlanRequest
    {
        public ApplyMode Mode { get; set; } = ApplyMode.CurrentPlan;
        public string? NewPlanName { get; set; } // Only used when Mode = NewPlan

        // Plan metadata
        public DateTimeOffset? StartTime { get; set; }
        public DateTimeOffset? EndTime { get; set; }
        public string? CurrencyCode { get; set; }

        // Itinerary: daily schedule
        public List<AIItineraryDay>? ItineraryDays { get; set; }

        // Budget: expense items
        public List<AIExpenseItem>? ExpenseItems { get; set; }

        // Packing lists
        public List<AIPackingList>? PackingLists { get; set; }

        // Notes
        public List<AINote>? Notes { get; set; }
    }

    public class AIItineraryDay
    {
        public int Order { get; set; } // 0-indexed day
        public string Title { get; set; } = string.Empty;
        public List<AIItineraryItem> Items { get; set; } = new();
    }

    public class AIItineraryItem
    {
        public string? PlaceId { get; set; } // Google Place ID (null for note-only items)
        public string PlaceName { get; set; } = string.Empty; // Fallback display name
        public string Role { get; set; } = string.Empty; // primary role (attraction, lunch, generic, etc.)
        public List<string>? Roles { get; set; } // all roles list
        public string StartTime { get; set; } = string.Empty; // "HH:MM" format
        public int Duration { get; set; } // Duration in minutes
        public string? Note { get; set; } // AI-generated context note
    }

    public class AIExpenseItem
    {
        public string Category { get; set; } = "Other"; // Maps to ExpenseCategory enum
        public string Name { get; set; } = string.Empty;
        public double Amount { get; set; }
    }

    public class AIPackingList
    {
        public string Name { get; set; } = string.Empty; // Category name (e.g. "Essentials")
        public List<string> Items { get; set; } = new(); // Item names
    }

    public class AINote
    {
        public string Title { get; set; } = string.Empty;
        public string Content { get; set; } = string.Empty;
    }
}
