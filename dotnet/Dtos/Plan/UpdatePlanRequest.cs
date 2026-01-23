using Microsoft.AspNetCore.Http;

namespace dotnet.Dtos.Plan
{
    public class UpdatePlanRequest
    {
        public string? Name { get; set; } = string.Empty;
        public DateTime? StartTime { get; set; }
        public DateTime? EndTime { get; set; }
        public double? Budget { get; set; }
        public string? CurrencyCode { get; set; } = "USD";
    }
}
