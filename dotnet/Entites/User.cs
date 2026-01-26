namespace dotnet.Domains
{
    public class User : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public string Username { get; set; } = string.Empty;
        public string PasswordHash { get; set; } = string.Empty;
        public string RefreshToken { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string AvatarUrl { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        
        public ICollection<Plan> Plans { get; set; } = new List<Plan>();
        public ICollection<Participant> Participations { get; set; } = new List<Participant>();
    }
}
