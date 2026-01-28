namespace dotnet.Entites
{
    public class PackingList : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid PlanId { get; set; }
        public string Name { get; set; } = string.Empty;
        //public int Order { get; set; }

        public Plan Plan { get; set; }
        public ICollection<PackingItem> PackingItems { get; set; } = new List<PackingItem>();
    }
}
