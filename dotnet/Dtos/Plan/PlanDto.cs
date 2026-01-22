namespace dotnet.Dtos.Plan
{
    public class PlanDto
    {
        public string Name { get; set; } = string.Empty;
        public DateTime StartTime { get; set; }
        public DateTime EndTime { get; set; }
        public double Budget { get; set; }
    }
}
