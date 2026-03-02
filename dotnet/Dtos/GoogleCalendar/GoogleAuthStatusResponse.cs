namespace dotnet.Dtos.GoogleCalendar
{
    public class GoogleAuthStatusResponse
    {
        public bool IsConnected { get; set; }
        public string? Email { get; set; }
        public string? AvatarUrl { get; set; }
    }
}
