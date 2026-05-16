using dotnet.Data;
using dotnet.Entites;
using dotnet.Dtos.Plan;
using dotnet.Dtos.Collaborator;
using dotnet.Enums;
using dotnet.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MongoDB.Driver;
using System.Security.Claims;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class PlanController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        private readonly ICurrentUser _currentUser;
        private readonly IMongoCollection<Place> _placesCollection;
        private readonly ICloudinaryService _cloudinaryService;
        private readonly IExternalApiService _externalApiService;
        public PlanController(MySQLDbContext mySQLDbContext, ICurrentUser currentUser,
            MongoDbService mongoDbService, ICloudinaryService cloudinaryService,
            IExternalApiService externalApiService)
        {
            dbContext = mySQLDbContext;
            _currentUser = currentUser;
            _placesCollection = mongoDbService.Database.GetCollection<Place>("Place");
            _cloudinaryService = cloudinaryService;
            _externalApiService = externalApiService;
        }

        [HttpGet]
        public async Task<IActionResult> GetAllPlans()
        {
            var userId = _currentUser.Id;
            if(userId == null)
            {
                return Unauthorized();
            }

            var results = await dbContext.Plans.Where(el => el.OwnerId == userId).ToListAsync();
            return Ok(results);
        }

        // Get Plan Detailed in Plans/{id} pages
        [HttpGet("{id:Guid}")]
        public async Task<ActionResult<PlanDto>> GetPlanById(Guid id)
        {
            var userId = _currentUser.Id;
            if(userId == null)
            {
                return Unauthorized();
            }

            var result = await dbContext.Plans
                .Where(el => el.Id == id)
                .Include(el => el.Owner)
                .Include(el => el.Notes)
                .Include(el => el.PackingLists)
                    .ThenInclude(pl => pl.PackingItems)
                .Include(el => el.ExpenseItems)
                .Include(el => el.Collaborators)
                    .ThenInclude(c => c.User)
                .Include(el => el.ItineraryDays)
                    .ThenInclude(iday => iday.ItineraryItems)
                .FirstOrDefaultAsync();

            if(result == null)
            {
                return NotFound();
            }

            // Access check: owner or accepted collaborator
            if (result.OwnerId != userId && !result.Collaborators.Any(c => c.UserId == userId && c.Status == InvitationStatus.Accepted))
            {
                return Forbid("You don't have access to this plan");
            }

            var placeIds = result.ItineraryDays
                .SelectMany(iday => iday.ItineraryItems)
                .Select(ii => ii.PlaceId)
                .Where(pid => pid != null)
                .Distinct()
                .ToList()!;

            var placesDict = await _placesCollection
                .Find(p => placeIds.Contains(p.PlaceId))
                .ToListAsync()
                .ContinueWith(t => t.Result.ToDictionary(p => p.PlaceId, p => p));

            return Ok(new PlanDto
            {
                Id = result.Id,
                OwnerId = result.OwnerId,
                OwnerName = result.Owner?.Name,
                OwnerUsername = result.Owner?.Username,
                OwnerAvatarUrl = result.Owner?.AvatarUrl,
                Name = result.Name,
                CoverImageUrl = result.CoverImageUrl,
                StartTime = result.StartTime,
                EndTime = result.EndTime,
                Budget = result.Budget,
                CurrencyCode = result.CurrencyCode,
                LastSyncGoogleCalendarAt = result.LastSyncGoogleCalendarAt,
                Notes = result.Notes
                    .OrderBy(note => note.CreatedAt)
                    .Select(note => new Dtos.Note.NoteDto
                {
                    Id = note.Id,
                    PlanId = note.PlanId,
                    Title = note.Title,
                    Content = note.Content
                }).ToList(),
                PackingLists = result.PackingLists
                    .OrderBy(list => list.CreatedAt)
                    .Select(pl => new Dtos.PackingList.PackingListDto
                    {
                        Id = pl.Id,
                        PlanId = pl.PlanId,
                        Name = pl.Name,
                        PackingItems = pl.PackingItems
                            .OrderBy(item => item.CreatedAt)
                            .Select(item => new Dtos.PackingItem.PackingItemDto
                            {
                                Id = item.Id,
                                PackingListId = item.PackingListId,
                                Name = item.Name,
                                IsPacked = item.IsPacked
                            }).ToList()
                    }).ToList(),
                ExpenseItems = result.ExpenseItems
                    .OrderBy(ei => ei.CreatedAt)
                    .Select(ei => new Dtos.ExpenseItem.ExpenseItemDto
                    {
                        Id = ei.Id,
                        PlanId = ei.PlanId,
                        Category = ei.Category,
                        Name = ei.Name,
                        Amount = ei.Amount,
                    }).ToList(),
                Collaborators = result.Collaborators.Select(c => new CollaboratorDto
                {
                    Id = c.Id,
                    UserId = c.UserId,
                    PlanId = c.PlanId,
                    Role = c.Role,
                    Status = c.Status,
                    Name = c.User.Name,
                    Username = c.User.Username,
                    AvatarUrl = c.User.AvatarUrl
                }).ToList(),
                ItineraryDays = result.ItineraryDays
                    .OrderBy(iday => iday.Order)
                    .Select(iday => new Dtos.ItineraryDay.ItineraryDayDto
                    {
                        Id = iday.Id,
                        PlanId = iday.PlanId,
                        Order = iday.Order,
                        Title = iday.Title,
                        ItineraryItems = iday.ItineraryItems
                            .Where(ii => !ii.IsDeleted)
                            .OrderBy(ii => ii.StartTime)
                            .Select(ii => new Dtos.ItineraryItem.ItineraryItemDto
                            {
                                Id = ii.Id,
                                ItineraryDayId = ii.ItineraryDayId,
                                Place = ii.PlaceId != null ? placesDict.GetValueOrDefault(ii.PlaceId) : null,
                                StartTime = ii.StartTime,
                                Duration = ii.Duration,
                                Note = ii.Note,
                                GoogleCalendarEventId = ii.GoogleCalendarEventId
                            }).ToList()
                    }).ToList()
            });
        }

        [HttpPost]
        public async Task<IActionResult> CreatePlan(CreatePlanRequest request)
        {
            var userId = _currentUser.Id;
            if(userId == null)
            {
                return Unauthorized();
            }

            var newPlan = new Plan
            {
                Id = Guid.NewGuid(),
                OwnerId = userId.Value,
                Name = request.Name,
                StartTime = request.StartTime,
                EndTime = request.EndTime,
                Budget = request.Budget,
                CurrencyCode = request.CurrencyCode
            };

            await dbContext.Plans.AddAsync(newPlan);

            var dateCount = (newPlan.EndTime - newPlan.StartTime).Days + 1;
            var itineraryDays = new List<ItineraryDay>(dateCount);
            for (int i = 0; i < dateCount; i++)
            {
                itineraryDays.Add(new ItineraryDay
                {
                    Id = Guid.NewGuid(),
                    PlanId = newPlan.Id,
                    Order = i,
                });
            }
            await dbContext.ItineraryDays.AddRangeAsync(itineraryDays);

            await dbContext.SaveChangesAsync();

            return CreatedAtAction(nameof(GetPlanById), new { id = newPlan.Id }, new PlanDto
            {
                Id = newPlan.Id,
                OwnerId = newPlan.OwnerId,
                Name = request.Name,
                StartTime = request.StartTime,
                EndTime = request.EndTime,
                Budget = request.Budget,
                CurrencyCode = request.CurrencyCode,
            });
        }

        // Handle updating plan details and adjusting itinerary days with itinerary items as well
        [HttpPatch("{id:Guid}")]
        public async Task<IActionResult> UpdatePlan(Guid id, UpdatePlanRequest request)
        {
            var userId = _currentUser.Id;
            if (userId == null) return Unauthorized();

            var plan = await dbContext.Plans
                .Where(el => el.Id == id)
                .Include(el => el.ItineraryDays)
                    .ThenInclude(iday => iday.ItineraryItems)
                .FirstOrDefaultAsync();
            if (plan == null)
            {
                return NotFound();
            }

            // Authorization: Owner or Editor collaborator
            if (plan.OwnerId != userId)
            {
                var collaborator = await dbContext.Collaborators
                    .FirstOrDefaultAsync(c => c.PlanId == id && c.UserId == userId && c.Status == InvitationStatus.Accepted && c.Role == PlanRole.Editor);
                if (collaborator == null)
                {
                    return Forbid("Only owner or editor can update plan");
                }
            }

            plan.Name = request.Name ?? plan.Name;
            plan.Budget = request.Budget ?? plan.Budget;
            plan.CurrencyCode = request.CurrencyCode ?? plan.CurrencyCode;

            var existingItineraryDays = plan.ItineraryDays;
            var newItineraryDays = existingItineraryDays.ToList();

            if (request.StartTime != null || request.EndTime != null)
            {
                var newStartTime = request.StartTime ?? plan.StartTime;
                var newEndTime = request.EndTime ?? plan.EndTime;
                if (newEndTime < newStartTime)
                {
                    return BadRequest("EndTime cannot be earlier than StartTime");
                }
                var newDateCount = (newEndTime - newStartTime).Days + 1;

                if (newDateCount > existingItineraryDays.Count)
                {
                    var daysToAdd = new List<ItineraryDay>();
                    for (int i = existingItineraryDays.Count; i < newDateCount; i++)
                    {
                        daysToAdd.Add(new ItineraryDay
                        {
                            Id = Guid.NewGuid(),
                            PlanId = plan.Id,
                            Order = i,
                        });
                    }
                    newItineraryDays = existingItineraryDays
                        .Concat(daysToAdd)
                        .ToList();
                    await dbContext.ItineraryDays.AddRangeAsync(daysToAdd);
                } else if(newDateCount < existingItineraryDays.Count)
                {
                    var daysToRemove = existingItineraryDays
                        .Where(iday => iday.Order >= newDateCount)
                        .ToList();

                    newItineraryDays = existingItineraryDays
                        .Where(iday => iday.Order < newDateCount)
                        .ToList();

                    dbContext.ItineraryDays.RemoveRange(daysToRemove);
                }

                plan.StartTime = request.StartTime ?? plan.StartTime;
                plan.EndTime = request.EndTime ?? plan.EndTime;
            }

            await dbContext.SaveChangesAsync();

            var placeIds = newItineraryDays
                .SelectMany(iday => iday.ItineraryItems)
                .Select(ii => ii.PlaceId)
                .Where(pid => pid != null)
                .Distinct()
                .ToList()!;

            var placesDict = await _placesCollection
                .Find(p => placeIds.Contains(p.PlaceId))
                .ToListAsync()
                .ContinueWith(t => t.Result.ToDictionary(p => p.PlaceId, p => p));

            return Ok(new PlanDto
            {
                Id = plan.Id,
                OwnerId = plan.OwnerId,
                Name = plan.Name,
                CoverImageUrl = plan.CoverImageUrl,
                StartTime = plan.StartTime,
                EndTime = plan.EndTime,
                Budget = plan.Budget,
                CurrencyCode = plan.CurrencyCode,
                LastSyncGoogleCalendarAt = plan.LastSyncGoogleCalendarAt,
                ItineraryDays = newItineraryDays.Select(iday => new Dtos.ItineraryDay.ItineraryDayDto
                {
                    Id = iday.Id,
                    PlanId = iday.PlanId,
                    Order = iday.Order,
                    Title = iday.Title,
                    ItineraryItems = iday.ItineraryItems
                        .Where(ii => !ii.IsDeleted)
                        .Select(ii => new Dtos.ItineraryItem.ItineraryItemDto
                    {
                        Id = ii.Id,
                        ItineraryDayId = ii.ItineraryDayId,
                        Place = ii.PlaceId != null ? placesDict.GetValueOrDefault(ii.PlaceId) : null,
                        StartTime = ii.StartTime,
                        Duration = ii.Duration,
                        Note = ii.Note,
                        GoogleCalendarEventId = ii.GoogleCalendarEventId
                    }).ToList()
                }).ToList()
            });
        }

        [HttpPatch("{id:Guid}/cover-image")]
        public async Task<IActionResult> UploadCoverImage(Guid id, IFormFile coverImage)
        {
            var userId = _currentUser.Id;
            if (userId == null) return Unauthorized();

            var plan = await dbContext.Plans
                .FirstOrDefaultAsync(p => p.Id == id);

            if (plan == null)
            {
                return NotFound();
            }

            // Authorization: Owner or Editor collaborator
            if (plan.OwnerId != userId)
            {
                var collaborator = await dbContext.Collaborators
                    .FirstOrDefaultAsync(c => c.PlanId == id && c.UserId == userId && c.Status == InvitationStatus.Accepted && c.Role == PlanRole.Editor);
                if (collaborator == null)
                {
                    return Forbid("Only owner or editor can update cover image");
                }
            }

            var uploadResult = await _cloudinaryService.UploadImageAsync(coverImage, id.ToString(), "Plans_Cover");
            if (uploadResult.Error != null)
            {
                return BadRequest(uploadResult.Error.Message);
            }

            plan.CoverImageUrl = uploadResult.SecureUrl.ToString();
            await dbContext.SaveChangesAsync();

            return Ok(new
            {
                coverImageUrl = plan.CoverImageUrl
            });
        }

        [HttpGet("mine")]
        public async Task<ActionResult<Helpers.PaginatedResult<PlanDto>>> GetMyPlans(
            int page = 1, int pageSize = 10,
            string? search = null,
            DateTimeOffset? dateFrom = null, DateTimeOffset? dateTo = null,
            string? status = null,
            string? sortBy = "startTime", string? sortOrder = "desc")
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }

            var query = dbContext.Plans.Where(p => p.OwnerId == userId)
                .Include(p => p.Collaborators)
                    .ThenInclude(collaborator => collaborator.User)
                .Include(p => p.Owner)
                .AsQueryable();

            // Search by name
            if (!string.IsNullOrWhiteSpace(search))
                query = query.Where(p => p.Name.Contains(search));

            // Date range filter
            if (dateFrom.HasValue)
                query = query.Where(p => p.StartTime >= dateFrom.Value);
            if (dateTo.HasValue)
                query = query.Where(p => p.StartTime <= dateTo.Value);

            // Status filter: upcoming (default) or past
            var now = DateTimeOffset.UtcNow;
            if (string.Equals(status, "past", StringComparison.OrdinalIgnoreCase))
                query = query.Where(p => p.StartTime <= now);
            else if (string.Equals(status, "upcoming", StringComparison.OrdinalIgnoreCase))
                query = query.Where(p => p.EndTime >= now);

            // Sort
            query = ApplyPlanSort(query, sortBy, sortOrder);

            var totalCount = await query.CountAsync();
            var plans = await query
                .Skip((page - 1) * pageSize)
                .Take(pageSize)
                .Select(p => new PlanDto
                {
                    Id = p.Id,
                    OwnerId = p.OwnerId,
                    OwnerName = p.Owner.Name,
                    OwnerUsername = p.Owner.Username,
                    OwnerAvatarUrl = p.Owner.AvatarUrl,
                    Name = p.Name,
                    CoverImageUrl = p.CoverImageUrl,
                    StartTime = p.StartTime,
                    EndTime = p.EndTime,
                    Budget = p.Budget,
                    CurrencyCode = p.CurrencyCode,
                    CreatedAt = p.CreatedAt,
                    Collaborators = p.Collaborators.Select(collaborator => new CollaboratorDto
                    {
                        Id = collaborator.Id,
                        UserId = collaborator.UserId,
                        PlanId = collaborator.PlanId,
                        Role = collaborator.Role,
                        Status = collaborator.Status,
                        Name = collaborator.User.Name,
                        Username = collaborator.User.Username,
                        AvatarUrl = collaborator.User.AvatarUrl
                    }).ToList()
                })
                .ToListAsync();

            return Ok(new Helpers.PaginatedResult<PlanDto>
            {
                Items = plans,
                TotalCount = totalCount,
                Page = page,
                PageSize = pageSize
            });
        }

        [HttpGet("shared")]
        public async Task<ActionResult<Helpers.PaginatedResult<PlanDto>>> GetSharedPlans(
            int page = 1, int pageSize = 10,
            string? search = null,
            DateTimeOffset? dateFrom = null, DateTimeOffset? dateTo = null,
            string? status = null,
            string? sortBy = "startTime", string? sortOrder = "desc")
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }

            var query = dbContext.Collaborators
                .Where(c => c.UserId == userId && c.Status == Enums.InvitationStatus.Accepted)
                .Include(c => c.Plan)
                    .ThenInclude(plan => plan.Collaborators)
                        .ThenInclude(collaborator => collaborator.User)
                .Include(c => c.Plan)
                    .ThenInclude(plan => plan.Owner)
                .AsQueryable();

            // Search by name
            if (!string.IsNullOrWhiteSpace(search))
                query = query.Where(p => p.Plan.Name.Contains(search));

            // Date range filter
            if (dateFrom.HasValue)
                query = query.Where(p => p.Plan.StartTime >= dateFrom.Value);
            if (dateTo.HasValue)
                query = query.Where(p => p.Plan.StartTime <= dateTo.Value);

            // Status filter
            var now = DateTimeOffset.UtcNow;
            if (string.Equals(status, "past", StringComparison.OrdinalIgnoreCase))
                query = query.Where(p => p.Plan.StartTime <= now);
            else if (string.Equals(status, "upcoming", StringComparison.OrdinalIgnoreCase))
                query = query.Where(p => p.Plan.EndTime >= now);

            // Sort
            query = ApplyCollaboratorPlanSort(query, sortBy, sortOrder);

            var totalCount = await query.CountAsync();
            var plans = await query
                .Skip((page - 1) * pageSize)
                .Take(pageSize)
                .ToListAsync();

            var results = plans
                .Select(p => new PlanDto
                {
                    Id = p.Plan.Id,
                    OwnerId = p.Plan.OwnerId,
                    OwnerName = p.Plan.Owner.Name,
                    OwnerUsername = p.Plan.Owner.Username,
                    OwnerAvatarUrl = p.Plan.Owner.AvatarUrl,
                    Name = p.Plan.Name,
                    CoverImageUrl = p.Plan.CoverImageUrl,
                    StartTime = p.Plan.StartTime,
                    EndTime = p.Plan.EndTime,
                    Budget = p.Plan.Budget,
                    CurrencyCode = p.Plan.CurrencyCode,
                    CreatedAt = p.Plan.CreatedAt,
                    Collaborators = p.Plan.Collaborators.Select(collaborator => new CollaboratorDto
                    {
                        Id = collaborator.Id,
                        UserId = collaborator.UserId,
                        PlanId = collaborator.PlanId,
                        Role = collaborator.Role,
                        Status = collaborator.Status,
                        Name = collaborator.User.Name,
                        Username = collaborator.User.Username,
                        AvatarUrl = collaborator.User.AvatarUrl
                    }).ToList(),
                    CollaboratorId = p.Plan.Collaborators
                        .FirstOrDefault(collaborator => collaborator.UserId == userId)?.Id
                })
                .ToList();

            return Ok(new Helpers.PaginatedResult<PlanDto>
            {
                Items = results,
                TotalCount = totalCount,
                Page = page,
                PageSize = pageSize
            });
        }

        [HttpGet("pending")]
        public async Task<ActionResult<Helpers.PaginatedResult<PlanDto>>> GetPendingInvitations(
            int page = 1, int pageSize = 10,
            string? search = null,
            DateTimeOffset? dateFrom = null, DateTimeOffset? dateTo = null,
            string? status = null,
            string? sortBy = "startTime", string? sortOrder = "desc")
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }

            var query = dbContext.Collaborators
                .Where(c => c.UserId == userId && c.Status == Enums.InvitationStatus.Pending)
                .Include(c => c.Plan)
                    .ThenInclude(plan => plan.Collaborators)
                        .ThenInclude(collaborator => collaborator.User)
                .Include(c => c.Plan)
                    .ThenInclude(plan => plan.Owner)
                .AsQueryable();

            // Search by name
            if (!string.IsNullOrWhiteSpace(search))
                query = query.Where(p => p.Plan.Name.Contains(search));

            // Date range filter
            if (dateFrom.HasValue)
                query = query.Where(p => p.Plan.StartTime >= dateFrom.Value);
            if (dateTo.HasValue)
                query = query.Where(p => p.Plan.StartTime <= dateTo.Value);

            // Status filter
            var now = DateTimeOffset.UtcNow;
            if (string.Equals(status, "past", StringComparison.OrdinalIgnoreCase))
                query = query.Where(p => p.Plan.StartTime <= now);
            else if (string.Equals(status, "upcoming", StringComparison.OrdinalIgnoreCase))
                query = query.Where(p => p.Plan.EndTime >= now);

            // Sort
            query = ApplyCollaboratorPlanSort(query, sortBy, sortOrder);

            var totalCount = await query.CountAsync();
            var plans = await query
                .Skip((page - 1) * pageSize)
                .Take(pageSize)
                .ToListAsync();

            var results = plans
                .Select(p => new PlanDto
                {
                    Id = p.Plan.Id,
                    OwnerId = p.Plan.OwnerId,
                    OwnerName = p.Plan.Owner.Name,
                    OwnerUsername = p.Plan.Owner.Username,
                    OwnerAvatarUrl = p.Plan.Owner.AvatarUrl,
                    Name = p.Plan.Name,
                    CoverImageUrl = p.Plan.CoverImageUrl,
                    StartTime = p.Plan.StartTime,
                    EndTime = p.Plan.EndTime,
                    Budget = p.Plan.Budget,
                    CurrencyCode = p.Plan.CurrencyCode,
                    CreatedAt = p.Plan.CreatedAt,
                    Collaborators = p.Plan.Collaborators.Select(collaborator => new CollaboratorDto
                    {
                        Id = collaborator.Id,
                        UserId = collaborator.UserId,
                        PlanId = collaborator.PlanId,
                        Role = collaborator.Role,
                        Status = collaborator.Status,
                        Name = collaborator.User.Name,
                        Username = collaborator.User.Username,
                        AvatarUrl = collaborator.User.AvatarUrl
                    }).ToList()
                }).ToList();

            return Ok(new Helpers.PaginatedResult<PlanDto>
            {
                Items = results,
                TotalCount = totalCount,
                Page = page,
                PageSize = pageSize
            });
        }

        /// <summary>
        /// Apply AI-generated plan data from a chat message to the current plan.
        /// Server reads GeneratedPlanData from the Message table — frontend only sends messageId + scope.
        /// </summary>
        [HttpPost("{id:Guid}/apply-ai")]
        public async Task<IActionResult> ApplyAIPlan(Guid id, [FromBody] ApplyAIPlanRequest request)
        {
            var userId = _currentUser.Id;
            if (userId == null) return Unauthorized();

            // ── Validate plan + authorization ──
            var plan = await dbContext.Plans.FirstOrDefaultAsync(p => p.Id == id);
            if (plan == null) return NotFound("Plan not found");

            if (plan.OwnerId != userId)
            {
                var collaborator = await dbContext.Collaborators
                    .FirstOrDefaultAsync(c => c.PlanId == id && c.UserId == userId
                        && c.Status == InvitationStatus.Accepted && c.Role == PlanRole.Editor);
                if (collaborator == null)
                    return Forbid("Only the owner or editor can apply AI plan");
            }

            // ── Read message from DB ──
            var message = await dbContext.Messages
                .FirstOrDefaultAsync(m => m.Id == request.MessageId);
            if (message?.GeneratedPlanData == null)
                return BadRequest("Message has no plan data");

            // ── Validate message belongs to this plan's conversation ──
            var conversation = await dbContext.Conversations
                .FirstOrDefaultAsync(c => c.Id == message.ConversationId && c.PlanId == id);
            if (conversation == null)
                return BadRequest("Message does not belong to this plan");

            // ── Parse GeneratedPlanData JSON ──
            System.Text.Json.JsonElement root;
            try
            {
                root = System.Text.Json.JsonDocument.Parse(message.GeneratedPlanData).RootElement;
            }
            catch
            {
                return BadRequest("Invalid GeneratedPlanData JSON");
            }

            if (!root.TryGetProperty("apply_data", out var applyData))
                return BadRequest("No apply_data found in message");

            var sections = applyData.TryGetProperty("sections", out var sec)
                ? sec : default;
            var planCtx = applyData.TryGetProperty("plan_context", out var ctx)
                ? ctx : default;

            bool applyAll = request.ApplyScope == ApplyScope.FullPlan;

            // ── Update plan metadata ──
            if (_tryGetString(planCtx, "startTime") is string st
                && DateTimeOffset.TryParse(st, out var startTime))
                plan.StartTime = startTime;
            if (_tryGetString(planCtx, "endTime") is string et
                && DateTimeOffset.TryParse(et, out var endTime))
                plan.EndTime = endTime;
            if (_tryGetString(planCtx, "currencyCode") is string cc)
                plan.CurrencyCode = cc;

            // ── Deserialize applicable sections ──
            var jsonOptions = new System.Text.Json.JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
            };

            var itineraryDays = _tryDeserializeSection<List<AIItineraryDay>>(
                sections, "itinerary", applyAll, jsonOptions);
            var expenseItems = _tryDeserializeSection<List<AIExpenseItem>>(
                sections, "budget", applyAll, jsonOptions);
            var packingLists = _tryDeserializeSection<List<AIPackingList>>(
                sections, "packing", applyAll, jsonOptions);
            var notes = _tryDeserializeSection<List<AINote>>(
                sections, "notes", applyAll, jsonOptions);

            // ── Apply Itinerary ──
            if (itineraryDays != null)
            {
                var existingDays = await dbContext.ItineraryDays
                    .Where(d => d.PlanId == plan.Id)
                    .Include(d => d.ItineraryItems)
                    .ToListAsync();
                dbContext.ItineraryDays.RemoveRange(existingDays);

                foreach (var aiDay in itineraryDays)
                {
                    var itineraryDay = new ItineraryDay
                    {
                        Id = Guid.NewGuid(),
                        PlanId = plan.Id,
                        Order = aiDay.Order,
                        Title = aiDay.Title,
                    };
                    await dbContext.ItineraryDays.AddAsync(itineraryDay);

                    foreach (var aiItem in aiDay.Items)
                    {
                        var placeId = aiItem.PlaceId;

                        // For restaurant stops with PlaceId, ensure place exists in MongoDB
                        if (!string.IsNullOrEmpty(placeId) && (aiItem.Role == "lunch" || aiItem.Role == "dinner"))
                        {
                            var existingPlace = await _placesCollection
                                .Find(p => p.PlaceId == placeId)
                                .FirstOrDefaultAsync();

                            if (existingPlace == null)
                            {
                                var googlePlace = await _externalApiService.GetPlaceDetailsAsync(placeId);
                                if (googlePlace != null)
                                {
                                    var raceCheck = await _placesCollection
                                        .Find(p => p.PlaceId == placeId)
                                        .FirstOrDefaultAsync();
                                    if (raceCheck == null)
                                    {
                                        googlePlace.Id = null;
                                        await _placesCollection.InsertOneAsync(googlePlace);
                                    }
                                }
                            }
                        }

                        TimeOnly startTimeVal = TimeOnly.MinValue;
                        if (!string.IsNullOrEmpty(aiItem.StartTime))
                            TimeOnly.TryParse(aiItem.StartTime, out startTimeVal);

                        var duration = TimeSpan.FromMinutes(aiItem.Duration > 0 ? aiItem.Duration : 60);

                        dbContext.ItineraryItems.Add(new ItineraryItem
                        {
                            Id = Guid.NewGuid(),
                            ItineraryDayId = itineraryDay.Id,
                            PlaceId = string.IsNullOrEmpty(placeId) ? null : placeId,
                            StartTime = startTimeVal,
                            Duration = duration,
                            Note = aiItem.Note,
                        });
                    }
                }
            }

            // ── Apply Budget ──
            if (expenseItems != null)
            {
                var existingExpenses = await dbContext.ExpenseItems
                    .Where(e => e.PlanId == plan.Id)
                    .ToListAsync();
                dbContext.ExpenseItems.RemoveRange(existingExpenses);

                foreach (var aiExpense in expenseItems)
                {
                    var category = Enum.TryParse<ExpenseCategory>(aiExpense.Category, true, out var parsed)
                        ? parsed : ExpenseCategory.Other;

                    dbContext.ExpenseItems.Add(new ExpenseItem
                    {
                        Id = Guid.NewGuid(),
                        PlanId = plan.Id,
                        Category = category,
                        Name = aiExpense.Name,
                        Amount = aiExpense.Amount,
                    });
                }
            }

            // ── Apply Packing Lists ──
            if (packingLists != null)
            {
                var existingPackingLists = await dbContext.PackingLists
                    .Where(p => p.PlanId == plan.Id)
                    .Include(p => p.PackingItems)
                    .ToListAsync();
                dbContext.PackingLists.RemoveRange(existingPackingLists);

                foreach (var aiPacking in packingLists)
                {
                    var packingList = new PackingList
                    {
                        Id = Guid.NewGuid(),
                        PlanId = plan.Id,
                        Name = aiPacking.Name,
                    };
                    await dbContext.PackingLists.AddAsync(packingList);

                    foreach (var itemName in aiPacking.Items)
                    {
                        dbContext.PackingItems.Add(new PackingItem
                        {
                            Id = Guid.NewGuid(),
                            PackingListId = packingList.Id,
                            Name = itemName,
                            IsPacked = false,
                        });
                    }
                }
            }

            // ── Apply Notes ──
            if (notes != null)
            {
                var existingNotes = await dbContext.Notes
                    .Where(n => n.PlanId == plan.Id)
                    .ToListAsync();
                dbContext.Notes.RemoveRange(existingNotes);

                foreach (var aiNote in notes)
                {
                    dbContext.Notes.Add(new Note
                    {
                        Id = Guid.NewGuid(),
                        PlanId = plan.Id,
                        Title = aiNote.Title,
                        Content = aiNote.Content,
                    });
                }
            }

            // ── Mark message as applied ──
            message.ApplyGeneratedPlanAt = DateTimeOffset.UtcNow;

            // ── Save all changes ──
            await dbContext.SaveChangesAsync();

            // ── Return full PlanDto ──
            var result = await dbContext.Plans
                .Where(p => p.Id == plan.Id)
                .Include(p => p.Owner)
                .Include(p => p.Notes)
                .Include(p => p.PackingLists)
                    .ThenInclude(pl => pl.PackingItems)
                .Include(p => p.ExpenseItems)
                .Include(p => p.Collaborators)
                    .ThenInclude(c => c.User)
                .Include(p => p.ItineraryDays)
                    .ThenInclude(iday => iday.ItineraryItems)
                .FirstOrDefaultAsync();

            if (result == null) return NotFound();

            var placeIds = result.ItineraryDays
                .SelectMany(iday => iday.ItineraryItems)
                .Select(ii => ii.PlaceId)
                .Where(pid => pid != null)
                .Distinct()
                .ToList()!;

            var placesDict = await _placesCollection
                .Find(p => placeIds.Contains(p.PlaceId))
                .ToListAsync()
                .ContinueWith(t => t.Result.ToDictionary(p => p.PlaceId, p => p));

            return Ok(new PlanDto
            {
                Id = result.Id,
                OwnerId = result.OwnerId,
                OwnerName = result.Owner?.Name,
                OwnerUsername = result.Owner?.Username,
                OwnerAvatarUrl = result.Owner?.AvatarUrl,
                Name = result.Name,
                CoverImageUrl = result.CoverImageUrl,
                StartTime = result.StartTime,
                EndTime = result.EndTime,
                Budget = result.Budget,
                CurrencyCode = result.CurrencyCode,
                LastSyncGoogleCalendarAt = result.LastSyncGoogleCalendarAt,
                Notes = result.Notes
                    .OrderBy(note => note.CreatedAt)
                    .Select(note => new Dtos.Note.NoteDto
                    {
                        Id = note.Id,
                        PlanId = note.PlanId,
                        Title = note.Title,
                        Content = note.Content
                    }).ToList(),
                PackingLists = result.PackingLists
                    .OrderBy(list => list.CreatedAt)
                    .Select(pl => new Dtos.PackingList.PackingListDto
                    {
                        Id = pl.Id,
                        PlanId = pl.PlanId,
                        Name = pl.Name,
                        PackingItems = pl.PackingItems
                            .OrderBy(item => item.CreatedAt)
                            .Select(item => new Dtos.PackingItem.PackingItemDto
                            {
                                Id = item.Id,
                                PackingListId = item.PackingListId,
                                Name = item.Name,
                                IsPacked = item.IsPacked
                            }).ToList()
                    }).ToList(),
                ExpenseItems = result.ExpenseItems
                    .OrderBy(ei => ei.CreatedAt)
                    .Select(ei => new Dtos.ExpenseItem.ExpenseItemDto
                    {
                        Id = ei.Id,
                        PlanId = ei.PlanId,
                        Category = ei.Category,
                        Name = ei.Name,
                        Amount = ei.Amount,
                    }).ToList(),
                Collaborators = result.Collaborators.Select(c => new CollaboratorDto
                {
                    Id = c.Id,
                    UserId = c.UserId,
                    PlanId = c.PlanId,
                    Role = c.Role,
                    Status = c.Status,
                    Name = c.User.Name,
                    Username = c.User.Username,
                    AvatarUrl = c.User.AvatarUrl
                }).ToList(),
                ItineraryDays = result.ItineraryDays
                    .OrderBy(iday => iday.Order)
                    .Select(iday => new Dtos.ItineraryDay.ItineraryDayDto
                    {
                        Id = iday.Id,
                        PlanId = iday.PlanId,
                        Order = iday.Order,
                        Title = iday.Title,
                        ItineraryItems = iday.ItineraryItems
                            .Where(ii => !ii.IsDeleted)
                            .OrderBy(ii => ii.StartTime)
                            .Select(ii => new Dtos.ItineraryItem.ItineraryItemDto
                            {
                                Id = ii.Id,
                                ItineraryDayId = ii.ItineraryDayId,
                                Place = ii.PlaceId != null ? placesDict.GetValueOrDefault(ii.PlaceId) : null,
                                StartTime = ii.StartTime,
                                Duration = ii.Duration,
                                Note = ii.Note,
                                GoogleCalendarEventId = ii.GoogleCalendarEventId
                            }).ToList()
                    }).ToList()
            });
        }

        // ── Apply helpers ─────────────────────────────────────────────

        private static T? _tryDeserializeSection<T>(
            System.Text.Json.JsonElement sections, string key, bool applyAll,
            System.Text.Json.JsonSerializerOptions jsonOptions) where T : class
        {
            if (sections.ValueKind != System.Text.Json.JsonValueKind.Object) return null;
            if (!sections.TryGetProperty(key, out var section)) return null;
            if (!applyAll)
            {
                if (!section.TryGetProperty("is_apply", out var flag) || !flag.GetBoolean())
                    return null;
            }
            if (!section.TryGetProperty("data", out var data)) return null;
            return System.Text.Json.JsonSerializer.Deserialize<T>(data.GetRawText(), jsonOptions);
        }

        private static string? _tryGetString(System.Text.Json.JsonElement el, string prop)
        {
            if (el.ValueKind != System.Text.Json.JsonValueKind.Object) return null;
            return el.TryGetProperty(prop, out var val) ? val.GetString() : null;
        }


        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeletePlan(Guid id)
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }

            var plan = await dbContext.Plans.FirstOrDefaultAsync(p => p.Id == id);

            if (plan == null)
            {
                return NotFound("Plan not found");
            }

            if (plan.OwnerId != userId)
            {
                return Forbid("Only the owner can delete this plan");
            }

            dbContext.Plans.Remove(plan);

            await dbContext.SaveChangesAsync();

            return NoContent();
        }
        // ── Sort helpers ─────────────────────────────────────────────
        private static IQueryable<Plan> ApplyPlanSort(IQueryable<Plan> query, string? sortBy, string? sortOrder)
        {
            var isAsc = string.Equals(sortOrder, "asc", StringComparison.OrdinalIgnoreCase);
            return sortBy?.ToLowerInvariant() switch
            {
                "createdat" => isAsc ? query.OrderBy(p => p.CreatedAt) : query.OrderByDescending(p => p.CreatedAt),
                "name" => isAsc ? query.OrderBy(p => p.Name) : query.OrderByDescending(p => p.Name),
                "starttime" => isAsc ? query.OrderBy(p => p.StartTime) : query.OrderByDescending(p => p.StartTime),
                _ => query.OrderByDescending(p => p.StartTime),
            };
        }

        private static IQueryable<Collaborator> ApplyCollaboratorPlanSort(IQueryable<Collaborator> query, string? sortBy, string? sortOrder)
        {
            var isAsc = string.Equals(sortOrder, "asc", StringComparison.OrdinalIgnoreCase);
            return sortBy?.ToLowerInvariant() switch
            {
                "createdat" => isAsc ? query.OrderBy(p => p.Plan.CreatedAt) : query.OrderByDescending(p => p.Plan.CreatedAt),
                "name" => isAsc ? query.OrderBy(p => p.Plan.Name) : query.OrderByDescending(p => p.Plan.Name),
                "starttime" => isAsc ? query.OrderBy(p => p.Plan.StartTime) : query.OrderByDescending(p => p.Plan.StartTime),
                _ => query.OrderByDescending(p => p.Plan.StartTime),
            };
        }

        // ── Clone Plan ───────────────────────────────────────────────
        [HttpPost("{id:Guid}/clone")]
        public async Task<IActionResult> ClonePlan(Guid id, [FromBody] ClonePlanRequest request)
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }

            // Validate user has access to the plan (owner or accepted collaborator)
            var sourcePlan = await dbContext.Plans
                .Where(p => p.Id == id)
                .Include(p => p.Notes)
                .Include(p => p.PackingLists)
                    .ThenInclude(pl => pl.PackingItems)
                .Include(p => p.ExpenseItems)
                .Include(p => p.ItineraryDays)
                    .ThenInclude(iday => iday.ItineraryItems)
                .FirstOrDefaultAsync();

            if (sourcePlan == null)
            {
                return NotFound("Plan not found");
            }

            var isOwner = sourcePlan.OwnerId == userId;
            var isCollaborator = await dbContext.Collaborators
                .AnyAsync(c => c.PlanId == id && c.UserId == userId && c.Status == InvitationStatus.Accepted);
            if (!isOwner && !isCollaborator)
            {
                return Forbid("You don't have access to this plan");
            }

            // Create new plan
            var newPlan = new Plan
            {
                Id = Guid.NewGuid(),
                OwnerId = userId.Value,
                Name = !string.IsNullOrWhiteSpace(request.Name) ? request.Name : $"Copy of \"{sourcePlan.Name}\"",
                CoverImageUrl = sourcePlan.CoverImageUrl,
                StartTime = sourcePlan.StartTime,
                EndTime = sourcePlan.EndTime,
                Budget = sourcePlan.Budget,
                CurrencyCode = sourcePlan.CurrencyCode,
            };
            await dbContext.Plans.AddAsync(newPlan);

            // Copy ItineraryDays + ItineraryItems
            foreach (var srcDay in sourcePlan.ItineraryDays)
            {
                var newDay = new ItineraryDay
                {
                    Id = Guid.NewGuid(),
                    PlanId = newPlan.Id,
                    Order = srcDay.Order,
                    Title = srcDay.Title,
                };
                await dbContext.ItineraryDays.AddAsync(newDay);

                foreach (var srcItem in srcDay.ItineraryItems.Where(ii => !ii.IsDeleted))
                {
                    dbContext.ItineraryItems.Add(new ItineraryItem
                    {
                        Id = Guid.NewGuid(),
                        ItineraryDayId = newDay.Id,
                        PlaceId = srcItem.PlaceId,
                        StartTime = srcItem.StartTime,
                        Duration = srcItem.Duration,
                        Note = srcItem.Note,
                    });
                }
            }

            // Copy ExpenseItems
            foreach (var srcExpense in sourcePlan.ExpenseItems)
            {
                dbContext.ExpenseItems.Add(new ExpenseItem
                {
                    Id = Guid.NewGuid(),
                    PlanId = newPlan.Id,
                    Category = srcExpense.Category,
                    Name = srcExpense.Name,
                    Amount = srcExpense.Amount,
                });
            }

            // Copy PackingLists + PackingItems
            foreach (var srcList in sourcePlan.PackingLists)
            {
                var newList = new PackingList
                {
                    Id = Guid.NewGuid(),
                    PlanId = newPlan.Id,
                    Name = srcList.Name,
                };
                await dbContext.PackingLists.AddAsync(newList);

                foreach (var srcItem in srcList.PackingItems)
                {
                    dbContext.PackingItems.Add(new PackingItem
                    {
                        Id = Guid.NewGuid(),
                        PackingListId = newList.Id,
                        Name = srcItem.Name,
                        IsPacked = false,
                    });
                }
            }

            // Copy Notes
            foreach (var srcNote in sourcePlan.Notes)
            {
                dbContext.Notes.Add(new Note
                {
                    Id = Guid.NewGuid(),
                    PlanId = newPlan.Id,
                    Title = srcNote.Title,
                    Content = srcNote.Content,
                });
            }

            await dbContext.SaveChangesAsync();

            return Ok(new { id = newPlan.Id, name = newPlan.Name });
        }
    }
}
