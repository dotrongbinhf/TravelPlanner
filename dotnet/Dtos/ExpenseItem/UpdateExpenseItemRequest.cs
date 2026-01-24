using dotnet.Enums;

namespace dotnet.Dtos.ExpenseItem
{
    public class UpdateExpenseItemRequest
    {
        public ExpenseCategory Category { get; set; }
        public string Name { get; set; }
        public double Amount { get; set; }
    }
}
