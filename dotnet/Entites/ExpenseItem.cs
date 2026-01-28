using dotnet.Enums;

namespace dotnet.Entites
{
    public class ExpenseItem : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public ExpenseCategory Category { get; set; } = ExpenseCategory.Other;
        public string Name { get; set; } = string.Empty;
        public double Amount { get; set; }
        //public int Order { get; set; }

        public Plan Plan { get; set; }
    }
}
