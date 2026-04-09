using dotnet.Interfaces;
using System.Net.Http.Headers;
using System.Text.Json;

namespace dotnet.Services
{
    public class GoogleCalendarService : IGoogleCalendarService
    {
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly IConfiguration _configuration;
        private readonly string _clientId;
        private readonly string _clientSecret;
        private readonly string _redirectUri;

        public GoogleCalendarService(IHttpClientFactory httpClientFactory, IConfiguration configuration)
        {
            _httpClientFactory = httpClientFactory;
            _configuration = configuration;
            _clientId = configuration["Google:ClientId"]!;
            _clientSecret = configuration["Google:ClientSecret"]!;
            _redirectUri = configuration["Google:RedirectUri"]!;
        }

        public async Task<(string AccessToken, string RefreshToken)> ExchangeCodeForTokensAsync(string code)
        {
            var client = _httpClientFactory.CreateClient();
            var content = new FormUrlEncodedContent(new Dictionary<string, string>
            {
                ["code"] = code,
                ["client_id"] = _clientId,
                ["client_secret"] = _clientSecret,
                ["redirect_uri"] = _redirectUri,
                ["grant_type"] = "authorization_code"
            });

            var response = await client.PostAsync("https://oauth2.googleapis.com/token", content);
            var responseBody = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                throw new ApplicationException($"Failed to exchange code for tokens: {responseBody}");
            }

            using var doc = JsonDocument.Parse(responseBody);
            var root = doc.RootElement;

            var accessToken = root.GetProperty("access_token").GetString()!;
            var refreshToken = root.TryGetProperty("refresh_token", out var rt) ? rt.GetString() ?? "" : "";

            return (accessToken, refreshToken);
        }

        public async Task<string> RefreshAccessTokenAsync(string refreshToken)
        {
            var client = _httpClientFactory.CreateClient();
            var content = new FormUrlEncodedContent(new Dictionary<string, string>
            {
                ["client_id"] = _clientId,
                ["client_secret"] = _clientSecret,
                ["refresh_token"] = refreshToken,
                ["grant_type"] = "refresh_token"
            });

            var response = await client.PostAsync("https://oauth2.googleapis.com/token", content);
            var responseBody = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                throw new ApplicationException($"Failed to refresh access token: {responseBody}");
            }

            using var doc = JsonDocument.Parse(responseBody);
            return doc.RootElement.GetProperty("access_token").GetString()!;
        }

        public async Task<GoogleUserInfo> GetUserInfoAsync(string accessToken)
        {
            var client = _httpClientFactory.CreateClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

            var response = await client.GetAsync("https://www.googleapis.com/oauth2/v2/userinfo");
            var responseBody = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                throw new ApplicationException($"Failed to get user info: {responseBody}");
            }

            using var doc = JsonDocument.Parse(responseBody);
            var root = doc.RootElement;

            return new GoogleUserInfo
            {
                Email = root.TryGetProperty("email", out var email) ? email.GetString() ?? "" : "",
                Picture = root.TryGetProperty("picture", out var picture) ? picture.GetString() : null
            };
        }

        public async Task<string> CreateEventAsync(string accessToken, GoogleCalendarEvent calendarEvent)
        {
            var client = _httpClientFactory.CreateClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

            var eventBody = new
            {
                summary = calendarEvent.Summary,
                description = calendarEvent.Description,
                location = calendarEvent.Location,
                start = calendarEvent.TimeZone != null 
                    ? new { dateTime = calendarEvent.Start.ToString("yyyy-MM-ddTHH:mm:ss"), timeZone = calendarEvent.TimeZone }
                    : new { dateTime = calendarEvent.Start.ToString("o"), timeZone = "UTC" },
                end = calendarEvent.TimeZone != null 
                    ? new { dateTime = calendarEvent.End.ToString("yyyy-MM-ddTHH:mm:ss"), timeZone = calendarEvent.TimeZone }
                    : new { dateTime = calendarEvent.End.ToString("o"), timeZone = "UTC" }
            };

            var json = JsonSerializer.Serialize(eventBody);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");

            var response = await client.PostAsync(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events", content);
            var responseBody = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                throw new ApplicationException($"Failed to create Google Calendar event: {responseBody}");
            }

            using var doc = JsonDocument.Parse(responseBody);
            return doc.RootElement.GetProperty("id").GetString()!;
        }

        public async Task UpdateEventAsync(string accessToken, string eventId, GoogleCalendarEvent calendarEvent)
        {
            var client = _httpClientFactory.CreateClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

            var eventBody = new
            {
                summary = calendarEvent.Summary,
                description = calendarEvent.Description,
                location = calendarEvent.Location,
                start = calendarEvent.TimeZone != null 
                    ? new { dateTime = calendarEvent.Start.ToString("yyyy-MM-ddTHH:mm:ss"), timeZone = calendarEvent.TimeZone }
                    : new { dateTime = calendarEvent.Start.ToString("o"), timeZone = "UTC" },
                end = calendarEvent.TimeZone != null 
                    ? new { dateTime = calendarEvent.End.ToString("yyyy-MM-ddTHH:mm:ss"), timeZone = calendarEvent.TimeZone }
                    : new { dateTime = calendarEvent.End.ToString("o"), timeZone = "UTC" }
            };

            var json = JsonSerializer.Serialize(eventBody);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");

            var response = await client.PutAsync(
                $"https://www.googleapis.com/calendar/v3/calendars/primary/events/{eventId}", content);

            if (!response.IsSuccessStatusCode)
            {
                var responseBody = await response.Content.ReadAsStringAsync();
                // If event not found (404), let caller handle re-creation
                if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
                {
                    throw new KeyNotFoundException($"Google Calendar event {eventId} not found");
                }
                throw new ApplicationException($"Failed to update Google Calendar event: {responseBody}");
            }
        }

        public async Task DeleteEventAsync(string accessToken, string eventId)
        {
            var client = _httpClientFactory.CreateClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

            var response = await client.DeleteAsync(
                $"https://www.googleapis.com/calendar/v3/calendars/primary/events/{eventId}");

            // 404 or 410 means already deleted, which is fine
            if (!response.IsSuccessStatusCode &&
                response.StatusCode != System.Net.HttpStatusCode.NotFound &&
                response.StatusCode != System.Net.HttpStatusCode.Gone)
            {
                var responseBody = await response.Content.ReadAsStringAsync();
                throw new ApplicationException($"Failed to delete Google Calendar event: {responseBody}");
            }
        }

        public async Task RevokeTokenAsync(string token)
        {
            try
            {
                var client = _httpClientFactory.CreateClient();
                var content = new FormUrlEncodedContent(new Dictionary<string, string>
                {
                    ["token"] = token
                });
                await client.PostAsync("https://oauth2.googleapis.com/revoke", content);
            }
            catch
            {
                // Best effort - don't fail if revoke fails
            }
        }
    }
}
