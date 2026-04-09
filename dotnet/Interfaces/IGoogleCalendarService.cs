namespace dotnet.Interfaces
{
    public interface IGoogleCalendarService
    {
        Task<(string AccessToken, string RefreshToken)> ExchangeCodeForTokensAsync(string code);
        Task<string> RefreshAccessTokenAsync(string refreshToken);
        Task<GoogleUserInfo> GetUserInfoAsync(string accessToken);
        Task<string> CreateEventAsync(string accessToken, GoogleCalendarEvent calendarEvent);
        Task UpdateEventAsync(string accessToken, string eventId, GoogleCalendarEvent calendarEvent);
        Task DeleteEventAsync(string accessToken, string eventId);
        Task RevokeTokenAsync(string token);
    }

    public class GoogleUserInfo
    {
        public string Email { get; set; } = string.Empty;
        public string? Picture { get; set; }
    }

    public class GoogleCalendarEvent
    {
        public string Summary { get; set; } = string.Empty;
        public string? Description { get; set; }
        public string? Location { get; set; }
        public DateTimeOffset Start { get; set; }
        public DateTimeOffset End { get; set; }
        public string? TimeZone { get; set; }
    }
}
