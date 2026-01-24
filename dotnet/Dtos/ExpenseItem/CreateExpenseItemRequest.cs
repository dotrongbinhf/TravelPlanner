using dotnet.Enums;

namespace dotnet.Dtos.ExpenseItem
{
    public class CreateExpenseItemRequest
    {
        public ExpenseCategory Category { get; set; } = ExpenseCategory.Other;
        public string Name { get; set; } = string.Empty;
        public double Amount { get; set; }
    }
}
