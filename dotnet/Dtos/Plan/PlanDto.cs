using dotnet.Domains;
using dotnet.Dtos.ExpenseItem;
using dotnet.Dtos.Note;
using dotnet.Dtos.PackingList;

namespace dotnet.Dtos.Plan
{
    public class PlanDto
    {
        public Guid Id { get; set; }
        public Guid OwnerId { get; set; }
        public string Name { get; set; } = string.Empty;
        public string CoverImageUrl { get; set; } = string.Empty;
        public DateTimeOffset StartTime { get; set; }
        public DateTimeOffset EndTime { get; set; }
        public double Budget { get; set; }
        public string CurrencyCode { get; set; } = "USD";

        public ICollection<NoteDto> Notes { get; set; } = new List<NoteDto>();
        public ICollection<PackingListDto> PackingLists { get; set; } = new List<PackingListDto>();
        public ICollection<ExpenseItemDto> ExpenseItems { get; set; } = new List<ExpenseItemDto>();

    }
}
