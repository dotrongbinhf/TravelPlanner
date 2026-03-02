using dotnet.Data;
using dotnet.Dtos.GoogleCalendar;
using dotnet.Entites;
using dotnet.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MongoDB.Driver;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class GoogleCalendarController : ControllerBase
    {
        private readonly MySQLDbContext _dbContext;
        private readonly ICurrentUser _currentUser;
        private readonly IGoogleCalendarService _googleCalendarService;
        private readonly IMongoCollection<Place> _placesCollection;

        public GoogleCalendarController(
            MySQLDbContext dbContext,
            ICurrentUser currentUser,
            IGoogleCalendarService googleCalendarService,
            MongoDbService mongoDbService)
        {
            _dbContext = dbContext;
            _currentUser = currentUser;
            _googleCalendarService = googleCalendarService;
            _placesCollection = mongoDbService.Database.GetCollection<Place>("Place");
        }

        [HttpPost("exchange-code")]
        public async Task<IActionResult> ExchangeCode(ExchangeGoogleCodeRequest request)
        {
            var userId = _currentUser.Id;
            if (userId == null) return Unauthorized();

            var user = await _dbContext.Users.FindAsync(userId.Value);
            if (user == null) return NotFound("User not found");

            try
            {
                var (accessToken, refreshToken) = await _googleCalendarService.ExchangeCodeForTokensAsync(request.Code);

                if (!string.IsNullOrEmpty(refreshToken))
                {
                    user.GoogleRefreshToken = refreshToken;
                }

                // Fetch Google user info
                try
                {
                    var userInfo = await _googleCalendarService.GetUserInfoAsync(accessToken);
                    user.GoogleEmail = userInfo.Email;
                    user.GoogleAvatarUrl = userInfo.Picture;
                }
                catch { /* Non-critical */ }

                await _dbContext.SaveChangesAsync();

                return Ok(new GoogleAuthStatusResponse
                {
                    IsConnected = true,
                    Email = user.GoogleEmail,
                    AvatarUrl = user.GoogleAvatarUrl
                });
            }
            catch (Exception ex)
            {
                return BadRequest($"Failed to exchange code: {ex.Message}");
            }
        }

        [HttpGet("auth-status")]
        public async Task<ActionResult<GoogleAuthStatusResponse>> GetAuthStatus()
        {
            var userId = _currentUser.Id;
            if (userId == null) return Unauthorized();

            var user = await _dbContext.Users.FindAsync(userId.Value);
            if (user == null) return NotFound("User not found");

            return Ok(new GoogleAuthStatusResponse
            {
                IsConnected = !string.IsNullOrEmpty(user.GoogleRefreshToken),
                Email = user.GoogleEmail,
                AvatarUrl = user.GoogleAvatarUrl
            });
        }

        [HttpPost("sync/{planId:Guid}")]
        public async Task<ActionResult<SyncGoogleCalendarResponse>> SyncCalendar(Guid planId)
        {
            var userId = _currentUser.Id;
            if (userId == null) return Unauthorized();

            var user = await _dbContext.Users.FindAsync(userId.Value);
            if (user == null) return NotFound("User not found");

            if (string.IsNullOrEmpty(user.GoogleRefreshToken))
            {
                return BadRequest("Google Calendar not connected. Please connect first.");
            }

            // Get plan with itinerary days and items (including soft-deleted)
            var plan = await _dbContext.Plans
                .Where(p => p.Id == planId)
                .Include(p => p.ItineraryDays)
                    .ThenInclude(d => d.ItineraryItems)
                .FirstOrDefaultAsync();

            if (plan == null) return NotFound("Plan not found");

            // Get access token
            string accessToken;
            try
            {
                accessToken = await _googleCalendarService.RefreshAccessTokenAsync(user.GoogleRefreshToken);
            }
            catch (Exception)
            {
                // Refresh token is invalid/revoked - clear it
                user.GoogleRefreshToken = null;
                await _dbContext.SaveChangesAsync();
                return BadRequest("Google Calendar session expired. Please reconnect.");
            }

            // Get all places for event details
            var allItems = plan.ItineraryDays.SelectMany(d => d.ItineraryItems).ToList();
            var placeIds = allItems.Select(i => i.PlaceId).Distinct().ToList();
            var placesDict = await _placesCollection
                .Find(p => placeIds.Contains(p.PlaceId))
                .ToListAsync()
                .ContinueWith(t => t.Result.ToDictionary(p => p.PlaceId, p => p));

            int createdCount = 0, updatedCount = 0, deletedCount = 0;
            var eventMappings = new List<EventMapping>();

            // 1. Handle soft-deleted items: delete from Google Calendar, then hard delete from DB
            var deletedItems = allItems.Where(i => i.IsDeleted).ToList();
            foreach (var item in deletedItems)
            {
                if (!string.IsNullOrEmpty(item.GoogleCalendarEventId))
                {
                    try
                    {
                        await _googleCalendarService.DeleteEventAsync(accessToken, item.GoogleCalendarEventId);
                    }
                    catch (Exception)
                    {
                        // Event might already be deleted, continue
                    }
                    deletedCount++;
                }
                _dbContext.ItineraryItems.Remove(item);
            }

            // 2. Handle active items
            var activeItems = allItems.Where(i => !i.IsDeleted).ToList();
            foreach (var item in activeItems)
            {
                var day = plan.ItineraryDays.First(d => d.Id == item.ItineraryDayId);
                var dayDate = plan.StartTime.AddDays(day.Order);
                var place = placesDict.GetValueOrDefault(item.PlaceId);

                var calendarEvent = new GoogleCalendarEvent
                {
                    Summary = place?.Title ?? "Itinerary Event",
                    Description = $"Category: {place?.Category ?? "N/A"}\nPlan: {plan.Name}\nDay {day.Order + 1}: {day.Title}",
                    Location = place?.Address,
                    Start = new DateTimeOffset(
                        dayDate.Year, dayDate.Month, dayDate.Day,
                        item.StartTime.Hour, item.StartTime.Minute, 0,
                        dayDate.Offset),
                    End = new DateTimeOffset(
                        dayDate.Year, dayDate.Month, dayDate.Day,
                        item.StartTime.Hour, item.StartTime.Minute, 0,
                        dayDate.Offset).Add(item.Duration)
                };

                if (!string.IsNullOrEmpty(item.GoogleCalendarEventId))
                {
                    // Try to update existing event
                    try
                    {
                        await _googleCalendarService.UpdateEventAsync(accessToken, item.GoogleCalendarEventId, calendarEvent);
                        updatedCount++;
                        eventMappings.Add(new EventMapping
                        {
                            ItineraryItemId = item.Id,
                            GoogleCalendarEventId = item.GoogleCalendarEventId
                        });
                    }
                    catch (KeyNotFoundException)
                    {
                        // Event was deleted from Google Calendar, create new one
                        var newEventId = await _googleCalendarService.CreateEventAsync(accessToken, calendarEvent);
                        item.GoogleCalendarEventId = newEventId;
                        createdCount++;
                        eventMappings.Add(new EventMapping
                        {
                            ItineraryItemId = item.Id,
                            GoogleCalendarEventId = newEventId
                        });
                    }
                }
                else
                {
                    // Create new event
                    var newEventId = await _googleCalendarService.CreateEventAsync(accessToken, calendarEvent);
                    item.GoogleCalendarEventId = newEventId;
                    createdCount++;
                    eventMappings.Add(new EventMapping
                    {
                        ItineraryItemId = item.Id,
                        GoogleCalendarEventId = newEventId
                    });
                }
            }

            // Update plan sync timestamp
            var syncedAt = DateTimeOffset.UtcNow;
            plan.LastSyncGoogleCalendarAt = syncedAt;
            await _dbContext.SaveChangesAsync();

            return Ok(new SyncGoogleCalendarResponse
            {
                SyncedAt = syncedAt,
                CreatedCount = createdCount,
                UpdatedCount = updatedCount,
                DeletedCount = deletedCount,
                EventMappings = eventMappings
            });
        }

        [HttpPost("disconnect")]
        public async Task<IActionResult> Disconnect()
        {
            var userId = _currentUser.Id;
            if (userId == null) return Unauthorized();

            var user = await _dbContext.Users.FindAsync(userId.Value);
            if (user == null) return NotFound("User not found");

            if (!string.IsNullOrEmpty(user.GoogleRefreshToken))
            {
                try 
                {
                    await _googleCalendarService.RevokeTokenAsync(user.GoogleRefreshToken);
                } 
                catch { /* Ignore */ }
            }
            
            user.GoogleRefreshToken = null;
            user.GoogleEmail = null;
            user.GoogleAvatarUrl = null;
            await _dbContext.SaveChangesAsync();

            return Ok(new GoogleAuthStatusResponse { IsConnected = false });
        }
    }
}
