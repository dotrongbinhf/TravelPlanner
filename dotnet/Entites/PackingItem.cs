namespace dotnet.Domains
{
    public class PackingItem : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid PackingListId { get; set; }
        //public Guid AssigneeId { get; set; }
        public string Name { get; set; } = string.Empty;
        //public int Quantity { get; set; }
        public bool IsPacked { get; set; }
        //public int Order { get; set; }

        public PackingList PackingList { get; set; }
        //public User Assignee { get; set; }
    }
}
