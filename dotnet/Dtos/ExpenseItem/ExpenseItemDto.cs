using dotnet.Enums;

namespace dotnet.Dtos.ExpenseItem
{
    public class ExpenseItemDto
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public ExpenseCategory Category { get; set; } = ExpenseCategory.Other;
        public string Name { get; set; } = string.Empty;
        public double Amount { get; set; }
    }
}
