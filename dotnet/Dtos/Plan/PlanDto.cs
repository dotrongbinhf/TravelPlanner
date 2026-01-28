using dotnet.Entites;
using dotnet.Dtos.ExpenseItem;
using dotnet.Dtos.Note;
using dotnet.Dtos.PackingList;
using dotnet.Dtos.Participant;
using dotnet.Dtos.User;
using dotnet.Dtos.ItineraryDay;

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

        // Pending and Shared Sections
        public Guid? ParticipantId { get; set; }

        public ICollection<NoteDto>? Notes { get; set; }
        public ICollection<PackingListDto>? PackingLists { get; set; }
        public ICollection<ExpenseItemDto>? ExpenseItems { get; set; }
        public ICollection<ParticipantDto>? Participants { get; set; }
        public ICollection<ItineraryDayDto>? ItineraryDays { get; set; }
    }
}
