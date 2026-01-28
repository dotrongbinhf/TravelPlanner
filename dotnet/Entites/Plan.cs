namespace dotnet.Entites
{
    public class Plan : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid OwnerId { get; set; }
        public string Name { get; set; } = string.Empty;
        public string CoverImageUrl { get; set; } = string.Empty;
        public DateTimeOffset StartTime { get; set; }
        public DateTimeOffset EndTime { get; set; }
        public double Budget { get; set; }
        public string CurrencyCode { get; set; } = "USD";

        public User Owner { get; set; }
        public ICollection<ItineraryDay> ItineraryDays { get; set; } = new List<ItineraryDay>();
        public ICollection<ExpenseItem> ExpenseItems { get; set; } = new List<ExpenseItem>();
        public ICollection<PackingList> PackingLists { get; set; } = new List<PackingList>();
        public ICollection<Note> Notes { get; set; } = new List<Note>();
        public ICollection<Participant> Participants { get; set; } = new List<Participant>();
    }
}
