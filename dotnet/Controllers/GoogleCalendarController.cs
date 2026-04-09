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
        public async Task<ActionResult<SyncGoogleCalendarResponse>> SyncCalendar(Guid planId, [FromQuery] int timeZoneOffsetMinutes = 0, [FromQuery] string timeZone = "UTC")
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
            var placeIds = allItems.Where(i => !string.IsNullOrEmpty(i.PlaceId)).Select(i => i.PlaceId).Distinct().ToList();
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
            var semaphore = new SemaphoreSlim(3);
            var syncTasks = activeItems.Select(async item =>
            {
                await semaphore.WaitAsync();
                try
                {
                    // plan.StartTime was sent as UTC. TimeZoneOffsetMinutes is the difference.
                    var localPlanStartTime = plan.StartTime.AddMinutes(-timeZoneOffsetMinutes);
                    var day = plan.ItineraryDays.First(d => d.Id == item.ItineraryDayId);
                    var dayDate = localPlanStartTime.AddDays(day.Order);
                    var place = string.IsNullOrEmpty(item.PlaceId) ? null : placesDict.GetValueOrDefault(item.PlaceId);

                    var startHour = item.StartTime?.Hour ?? 9;
                    var startMinute = item.StartTime?.Minute ?? 0;
                    var duration = item.Duration ?? TimeSpan.FromHours(1);

                    var calendarEvent = new GoogleCalendarEvent
                    {
                        Summary = place?.Title ?? item.Note ?? "Itinerary Event",
                        Description = $"Category: {place?.Category ?? "N/A"}\nPlan: {plan.Name}\nDay {day.Order + 1}: {day.Title}\nNote: {item.Note}",
                        Location = place?.Address,
                        Start = new DateTimeOffset(
                            dayDate.Year, dayDate.Month, dayDate.Day,
                            startHour, startMinute, 0,
                            TimeSpan.Zero),
                        End = new DateTimeOffset(
                            dayDate.Year, dayDate.Month, dayDate.Day,
                            startHour, startMinute, 0,
                            TimeSpan.Zero).Add(duration),
                        TimeZone = timeZone
                    };

                    if (!string.IsNullOrEmpty(item.GoogleCalendarEventId))
                    {
                        try
                        {
                            await _googleCalendarService.UpdateEventAsync(accessToken, item.GoogleCalendarEventId, calendarEvent);
                            Interlocked.Increment(ref updatedCount);
                            lock (eventMappings)
                            {
                                eventMappings.Add(new EventMapping
                                {
                                    ItineraryItemId = item.Id,
                                    GoogleCalendarEventId = item.GoogleCalendarEventId
                                });
                            }
                        }
                        catch (KeyNotFoundException)
                        {
                            var newEventId = await _googleCalendarService.CreateEventAsync(accessToken, calendarEvent);
                            item.GoogleCalendarEventId = newEventId;
                            Interlocked.Increment(ref createdCount);
                            lock (eventMappings)
                            {
                                eventMappings.Add(new EventMapping
                                {
                                    ItineraryItemId = item.Id,
                                    GoogleCalendarEventId = newEventId
                                });
                            }
                        }
                    }
                    else
                    {
                        var newEventId = await _googleCalendarService.CreateEventAsync(accessToken, calendarEvent);
                        item.GoogleCalendarEventId = newEventId;
                        Interlocked.Increment(ref createdCount);
                        lock (eventMappings)
                        {
                            eventMappings.Add(new EventMapping
                            {
                                ItineraryItemId = item.Id,
                                GoogleCalendarEventId = newEventId
                            });
                        }
                    }
                }
                finally
                {
                    semaphore.Release();
                }
            });

            await Task.WhenAll(syncTasks);

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

        [HttpPost("unsync/{planId:Guid}")]
        public async Task<IActionResult> UnsyncCalendar(Guid planId)
        {
            var userId = _currentUser.Id;
            if (userId == null) return Unauthorized();

            var user = await _dbContext.Users.FindAsync(userId.Value);
            if (user == null) return NotFound("User not found");

            if (string.IsNullOrEmpty(user.GoogleRefreshToken))
            {
                return BadRequest("Google Calendar not connected.");
            }

            var plan = await _dbContext.Plans
                .Where(p => p.Id == planId)
                .Include(p => p.ItineraryDays)
                    .ThenInclude(d => d.ItineraryItems)
                .FirstOrDefaultAsync();

            if (plan == null) return NotFound("Plan not found");

            string accessToken;
            try
            {
                accessToken = await _googleCalendarService.RefreshAccessTokenAsync(user.GoogleRefreshToken);
            }
            catch (Exception)
            {
                user.GoogleRefreshToken = null;
                await _dbContext.SaveChangesAsync();
                return BadRequest("Google Calendar session expired. Please reconnect.");
            }

            var allItems = plan.ItineraryDays.SelectMany(d => d.ItineraryItems).ToList();
            var syncedItems = allItems.Where(i => !string.IsNullOrEmpty(i.GoogleCalendarEventId)).ToList();
            
            var semaphore = new SemaphoreSlim(3);
            var unsyncTasks = syncedItems.Select(async item =>
            {
                await semaphore.WaitAsync();
                try
                {
                    try
                    {
                        await _googleCalendarService.DeleteEventAsync(accessToken, item.GoogleCalendarEventId);
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"Failed to delete event {item.GoogleCalendarEventId} from Google Calendar: {ex.Message}");
                    }
                    // Only detach if we didn't crash before this point
                    item.GoogleCalendarEventId = null;
                }
                finally
                {
                    semaphore.Release();
                }
            });

            await Task.WhenAll(unsyncTasks);

            plan.LastSyncGoogleCalendarAt = null;
            await _dbContext.SaveChangesAsync();

            return Ok(new { Message = "Unsynced successfully" });
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
