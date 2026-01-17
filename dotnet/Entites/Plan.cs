namespace dotnet.Domains
{
    public class Plan : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid OwnerId { get; set; }
        public string Title { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;
        public string CoverImageUrl { get; set; } = string.Empty;
        public DateTime StartTime { get; set; }
        public DateTime EndTime { get; set; }
        public double Budget { get; set; }

        public ICollection<ItineraryItem> ItineraryItems { get; set; } = new List<ItineraryItem>();
        public ICollection<ExpenseItem> ExpenseItems { get; set; } = new List<ExpenseItem>();
        public ICollection<PackingList> PackingLists { get; set; } = new List<PackingList>();
        public ICollection<Note> Notes { get; set; } = new List<Note>();
        public ICollection<Participant> Participants { get; set; } = new List<Participant>();
    }
}
