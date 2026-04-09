using dotnet.Data;
using dotnet.Entites;
using dotnet.Dtos.Plan;
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
                .Include(el => el.Notes)
                .Include(el => el.PackingLists)
                    .ThenInclude(pl => pl.PackingItems)
                .Include(el => el.ExpenseItems)
                .Include(el => el.Participants)
                    .ThenInclude(p => p.User)
                .Include(el => el.ItineraryDays)
                    .ThenInclude(iday => iday.ItineraryItems)
                .FirstOrDefaultAsync();

            if(result == null)
            {
                return NotFound();
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
                        GroupName = ei.GroupName,
                    }).ToList(),
                Participants = result.Participants.Select(p => new Dtos.Participant.ParticipantDto
                {
                    Id = p.Id,
                    UserId = p.UserId,
                    PlanId = p.PlanId,
                    Role = p.Role,
                    Status = p.Status,
                    Name = p.User.Name,
                    Username = p.User.Username,
                    AvatarUrl = p.User.AvatarUrl
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

            var participant = new Participant
            {
                Id = Guid.NewGuid(),
                PlanId = newPlan.Id,
                UserId = userId.Value,
                Role = Enums.PlanRole.Owner,
                Status = Enums.InvitationStatus.Accepted
            };
            await dbContext.Participants.AddAsync(participant);

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
                Participants = new List<Dtos.Participant.ParticipantDto>
                {
                    new Dtos.Participant.ParticipantDto
                    {
                        Id = participant.Id,
                        UserId = participant.UserId,
                        PlanId = participant.PlanId,
                        Role = participant.Role,
                        Status = participant.Status
                    }
                }
            });
        }

        // Handle updating plan details and adjusting itinerary days with itinerary items as well
        [HttpPatch("{id:Guid}")]
        public async Task<IActionResult> UpdatePlan(Guid id, UpdatePlanRequest request)
        {
            var plan = await dbContext.Plans
                .Where(el => el.Id == id)
                .Include(el => el.ItineraryDays)
                    .ThenInclude(iday => iday.ItineraryItems)
                .FirstOrDefaultAsync();
            if (plan == null)
            {
                return NotFound();
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
            var plan = await dbContext.Plans
                .FirstOrDefaultAsync(p => p.Id == id);

            if (plan == null)
            {
                return NotFound();
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
        public async Task<ActionResult<Helpers.PaginatedResult<PlanDto>>> GetMyPlans(int page = 1, int pageSize = 10)
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }

            var query = dbContext.Plans.Where(p => p.OwnerId == userId)
                .Include(p => p.Participants)
                    .ThenInclude(participant => participant.User);
            var totalCount = await query.CountAsync();
            var plans = await query
                .OrderByDescending(p => p.StartTime)
                .Skip((page - 1) * pageSize)
                .Take(pageSize)
                .Select(p => new PlanDto
                {
                    Id = p.Id,
                    OwnerId = p.OwnerId,
                    Name = p.Name,
                    CoverImageUrl = p.CoverImageUrl,
                    StartTime = p.StartTime,
                    EndTime = p.EndTime,
                    Budget = p.Budget,
                    CurrencyCode = p.CurrencyCode,
                    Participants = p.Participants.Select(participant => new Dtos.Participant.ParticipantDto
                    {
                        Id = participant.Id,
                        UserId = participant.UserId,
                        PlanId = participant.PlanId,
                        Role = participant.Role,
                        Status = participant.Status,
                        Name = participant.User.Name,
                        Username = participant.User.Username,
                        AvatarUrl = participant.User.AvatarUrl
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
        public async Task<ActionResult<Helpers.PaginatedResult<PlanDto>>> GetSharedPlans(int page = 1, int pageSize = 10)
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }

            var query = dbContext.Participants
                .Where(p => p.UserId == userId && p.Status == Enums.InvitationStatus.Accepted && p.Role != Enums.PlanRole.Owner)
                .Include(p => p.Plan)
                    .ThenInclude(plan => plan.Participants)
                        .ThenInclude(participant => participant.User);

            var totalCount = await query.CountAsync();
            var plans = await query
                .OrderByDescending(p => p.Plan.StartTime)
                .Skip((page - 1) * pageSize)
                .Take(pageSize)
                .ToListAsync();

            var results = plans
                .Select(p => new PlanDto
                {
                    Id = p.Plan.Id,
                    OwnerId = p.Plan.OwnerId,
                    Name = p.Plan.Name,
                    CoverImageUrl = p.Plan.CoverImageUrl,
                    StartTime = p.Plan.StartTime,
                    EndTime = p.Plan.EndTime,
                    Budget = p.Plan.Budget,
                    CurrencyCode = p.Plan.CurrencyCode,
                    Participants = p.Plan.Participants.Select(participant => new Dtos.Participant.ParticipantDto
                    {
                        Id = participant.Id,
                        UserId = participant.UserId,
                        PlanId = participant.PlanId,
                        Role = participant.Role,
                        Status = participant.Status,
                        Name = participant.User.Name,
                        Username = participant.User.Username,
                        AvatarUrl = participant.User.AvatarUrl
                    }).ToList(),
                    ParticipantId = p.Plan.Participants
                        .FirstOrDefault(participant => participant.UserId == userId)?.Id
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
        public async Task<ActionResult<Helpers.PaginatedResult<PlanDto>>> GetPendingInvitations(int page = 1, int pageSize = 10)
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }

            var query = dbContext.Participants
                .Where(p => p.UserId == userId && p.Status == Enums.InvitationStatus.Pending)
                .Include(p => p.Plan)
                    .ThenInclude(plan => plan.Participants)
                        .ThenInclude(participant => participant.User);

            var totalCount = await query.CountAsync();
            var plans = await query
                .OrderByDescending(p => p.CreatedAt)
                .Skip((page - 1) * pageSize)
                .Take(pageSize)
                .ToListAsync();

            var results = plans
                .Select(p => new PlanDto
                {
                    Id = p.Plan.Id,
                    OwnerId = p.Plan.OwnerId,
                    Name = p.Plan.Name,
                    CoverImageUrl = p.Plan.CoverImageUrl,
                    StartTime = p.Plan.StartTime,
                    EndTime = p.Plan.EndTime,
                    Budget = p.Plan.Budget,
                    CurrencyCode = p.Plan.CurrencyCode,
                    Participants = p.Plan.Participants.Select(participant => new Dtos.Participant.ParticipantDto
                    {
                        Id = participant.Id,
                        UserId = participant.UserId,
                        PlanId = participant.PlanId,
                        Role = participant.Role,
                        Status = participant.Status,
                        Name = participant.User.Name,
                        Username = participant.User.Username,
                        AvatarUrl = participant.User.AvatarUrl
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
        /// Apply AI-generated plan data to an existing plan (replace) or create a new plan.
        /// Handles: itinerary (with PlaceId resolution for restaurants), budget, packing lists, notes.
        /// </summary>
        [HttpPost("{id:Guid}/apply-ai")]
        public async Task<IActionResult> ApplyAIPlan(Guid id, [FromBody] ApplyAIPlanRequest request)
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }

            // Validate source plan exists and user owns it
            var sourcePlan = await dbContext.Plans.FirstOrDefaultAsync(p => p.Id == id);
            if (sourcePlan == null)
            {
                return NotFound("Plan not found");
            }
            if (sourcePlan.OwnerId != userId)
            {
                return Forbid("Only the owner can apply AI plan");
            }

            Plan targetPlan;

            if (request.Mode == ApplyMode.NewPlan)
            {
                // Create a new plan
                targetPlan = new Plan
                {
                    Id = Guid.NewGuid(),
                    OwnerId = userId.Value,
                    Name = request.NewPlanName ?? $"{sourcePlan.Name} (AI)",
                    StartTime = request.StartTime ?? sourcePlan.StartTime,
                    EndTime = request.EndTime ?? sourcePlan.EndTime,
                    Budget = sourcePlan.Budget,
                    CurrencyCode = request.CurrencyCode ?? sourcePlan.CurrencyCode,
                };
                await dbContext.Plans.AddAsync(targetPlan);

                // Add owner as participant
                await dbContext.Participants.AddAsync(new Participant
                {
                    Id = Guid.NewGuid(),
                    PlanId = targetPlan.Id,
                    UserId = userId.Value,
                    Role = PlanRole.Owner,
                    Status = InvitationStatus.Accepted,
                });
            }
            else
            {
                targetPlan = sourcePlan;

                // Update plan metadata
                if (request.StartTime.HasValue)
                    targetPlan.StartTime = request.StartTime.Value;
                if (request.EndTime.HasValue)
                    targetPlan.EndTime = request.EndTime.Value;
                if (!string.IsNullOrEmpty(request.CurrencyCode))
                    targetPlan.CurrencyCode = request.CurrencyCode;

                // Delete existing data (cascade will handle children)
                var existingDays = await dbContext.ItineraryDays
                    .Where(d => d.PlanId == targetPlan.Id)
                    .Include(d => d.ItineraryItems)
                    .ToListAsync();
                dbContext.ItineraryDays.RemoveRange(existingDays);

                var existingExpenses = await dbContext.ExpenseItems
                    .Where(e => e.PlanId == targetPlan.Id)
                    .ToListAsync();
                dbContext.ExpenseItems.RemoveRange(existingExpenses);

                var existingPackingLists = await dbContext.PackingLists
                    .Where(p => p.PlanId == targetPlan.Id)
                    .Include(p => p.PackingItems)
                    .ToListAsync();
                dbContext.PackingLists.RemoveRange(existingPackingLists);

                var existingNotes = await dbContext.Notes
                    .Where(n => n.PlanId == targetPlan.Id)
                    .ToListAsync();
                dbContext.Notes.RemoveRange(existingNotes);
            }

            // ── Apply Itinerary ──────────────────────────────────────
            if (request.ItineraryDays != null)
            {
                foreach (var aiDay in request.ItineraryDays)
                {
                    var itineraryDay = new ItineraryDay
                    {
                        Id = Guid.NewGuid(),
                        PlanId = targetPlan.Id,
                        Order = aiDay.Order,
                        Title = aiDay.Title,
                    };
                    await dbContext.ItineraryDays.AddAsync(itineraryDay);

                    foreach (var aiItem in aiDay.Items)
                    {
                        var placeId = aiItem.PlaceId;

                        // For restaurant stops (lunch/dinner) with PlaceId, ensure place exists in MongoDB
                        if (!string.IsNullOrEmpty(placeId) && (aiItem.Role == "lunch" || aiItem.Role == "dinner"))
                        {
                            var existingPlace = await _placesCollection
                                .Find(p => p.PlaceId == placeId)
                                .FirstOrDefaultAsync();

                            if (existingPlace == null)
                            {
                                // Fetch from Google Places API and save to MongoDB
                                var googlePlace = await _externalApiService.GetPlaceDetailsAsync(placeId);
                                if (googlePlace != null)
                                {
                                    // Check for race condition
                                    var raceCheck = await _placesCollection
                                        .Find(p => p.PlaceId == placeId)
                                        .FirstOrDefaultAsync();
                                    if (raceCheck == null)
                                    {
                                        googlePlace.Id = null; // Let MongoDB generate the Id
                                        await _placesCollection.InsertOneAsync(googlePlace);
                                    }
                                }
                            }
                        }

                        // Parse StartTime and Duration
                        TimeOnly startTime = TimeOnly.MinValue;
                        if (!string.IsNullOrEmpty(aiItem.StartTime))
                        {
                            TimeOnly.TryParse(aiItem.StartTime, out startTime);
                        }

                        var duration = TimeSpan.FromMinutes(aiItem.Duration > 0 ? aiItem.Duration : 60);

                        var itineraryItem = new ItineraryItem
                        {
                            Id = Guid.NewGuid(),
                            ItineraryDayId = itineraryDay.Id,
                            PlaceId = string.IsNullOrEmpty(placeId) ? null : placeId,
                            StartTime = startTime,
                            Duration = duration,
                            Note = aiItem.Note,
                        };
                        dbContext.ItineraryItems.Add(itineraryItem);
                    }
                }
            }

            // ── Apply Budget / Expense Items ─────────────────────────
            if (request.ExpenseItems != null)
            {
                foreach (var aiExpense in request.ExpenseItems)
                {
                    var category = Enum.TryParse<ExpenseCategory>(aiExpense.Category, true, out var parsed)
                        ? parsed
                        : ExpenseCategory.Other;

                    var expenseItem = new ExpenseItem
                    {
                        Id = Guid.NewGuid(),
                        PlanId = targetPlan.Id,
                        Category = category,
                        Name = aiExpense.Name,
                        Amount = aiExpense.Amount,
                        GroupName = aiExpense.GroupName,
                    };
                    dbContext.ExpenseItems.Add(expenseItem);

                }
            }

            // ── Apply Packing Lists ──────────────────────────────────
            if (request.PackingLists != null)
            {
                foreach (var aiPacking in request.PackingLists)
                {
                    var packingList = new PackingList
                    {
                        Id = Guid.NewGuid(),
                        PlanId = targetPlan.Id,
                        Name = aiPacking.Name,
                    };
                    await dbContext.PackingLists.AddAsync(packingList);

                    foreach (var itemName in aiPacking.Items)
                    {
                        var packingItem = new PackingItem
                        {
                            Id = Guid.NewGuid(),
                            PackingListId = packingList.Id,
                            Name = itemName,
                            IsPacked = false,
                        };
                        dbContext.PackingItems.Add(packingItem);
                    }
                }
            }

            // ── Apply Notes ──────────────────────────────────────────
            if (request.Notes != null)
            {
                foreach (var aiNote in request.Notes)
                {
                    var note = new Note
                    {
                        Id = Guid.NewGuid(),
                        PlanId = targetPlan.Id,
                        Title = aiNote.Title,
                        Content = aiNote.Content,
                    };
                    dbContext.Notes.Add(note);
                }
            }

            // ── Save all changes ─────────────────────────────────────
            await dbContext.SaveChangesAsync();

            // ── Return full PlanDto ──────────────────────────────────
            var result = await dbContext.Plans
                .Where(p => p.Id == targetPlan.Id)
                .Include(p => p.Notes)
                .Include(p => p.PackingLists)
                    .ThenInclude(pl => pl.PackingItems)
                .Include(p => p.ExpenseItems)
                .Include(p => p.Participants)
                    .ThenInclude(p => p.User)
                .Include(p => p.ItineraryDays)
                    .ThenInclude(iday => iday.ItineraryItems)
                .FirstOrDefaultAsync();

            if (result == null)
            {
                return NotFound();
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
                        GroupName = ei.GroupName,
                    }).ToList(),
                Participants = result.Participants.Select(p => new Dtos.Participant.ParticipantDto
                {
                    Id = p.Id,
                    UserId = p.UserId,
                    PlanId = p.PlanId,
                    Role = p.Role,
                    Status = p.Status,
                    Name = p.User.Name,
                    Username = p.User.Username,
                    AvatarUrl = p.User.AvatarUrl
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
    }
}
