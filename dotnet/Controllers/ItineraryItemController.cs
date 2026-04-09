using dotnet.Data;
using dotnet.Dtos.ItineraryItem;
using dotnet.Entites;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MongoDB.Driver;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class ItineraryItemController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        private readonly IMongoCollection<Place> _placesCollection;
        public ItineraryItemController(MySQLDbContext mySQLDbContext, MongoDbService mongoDbService)
        {
            dbContext = mySQLDbContext;
            _placesCollection = mongoDbService.Database.GetCollection<Place>("Place");
        }

        [HttpGet("{id:Guid}")]
        public async Task<ActionResult<ItineraryItemDto>> GetItineraryItemById(Guid id)
        {
            var itineraryItem = await dbContext.ItineraryItems.FindAsync(id);
            if (itineraryItem == null)
            {
                return NotFound();
            }

            Place? place = null;
            if (!string.IsNullOrEmpty(itineraryItem.PlaceId))
            {
                place = await _placesCollection.Find(p => p.PlaceId == itineraryItem.PlaceId).FirstOrDefaultAsync();
            }

            return Ok(new ItineraryItemDto
            {
                Id = itineraryItem.Id,
                ItineraryDayId = itineraryItem.ItineraryDayId,
                Place = place,
                StartTime = itineraryItem.StartTime,
                Duration = itineraryItem.Duration,
                Note = itineraryItem.Note,
            });
        }

        [HttpPost]
        public async Task<ActionResult<ItineraryItemDto>> CreateItineraryItem(Guid itineraryDayId, CreateItineraryItemRequest request)
        {
            var itineraryDay = await dbContext.ItineraryDays.FindAsync(itineraryDayId);
            if (itineraryDay == null)
            {
                return NotFound();
            }

            // Must have either PlaceId or Note
            if (string.IsNullOrEmpty(request.PlaceId) && string.IsNullOrEmpty(request.Note))
            {
                return BadRequest("Either PlaceId or Note must be provided.");
            }

            Place? place = null;
            if (!string.IsNullOrEmpty(request.PlaceId))
            {
                place = await _placesCollection.Find(p => p.PlaceId == request.PlaceId).FirstOrDefaultAsync();
                if (place == null)
                {
                    return NotFound("Place not found.");
                }
            }

            var itineraryItem = new ItineraryItem
            {
                Id = Guid.NewGuid(),
                ItineraryDayId = itineraryDayId,
                PlaceId = string.IsNullOrEmpty(request.PlaceId) ? null : request.PlaceId,
                StartTime = request.StartTime,
                Duration = request.Duration,
                Note = request.Note,
            };

            dbContext.ItineraryItems.Add(itineraryItem);
            await dbContext.SaveChangesAsync();

            return CreatedAtAction(nameof(GetItineraryItemById), new { id = itineraryItem.Id }, new ItineraryItemDto
            {
                Id = itineraryItem.Id,
                ItineraryDayId = itineraryItem.ItineraryDayId,
                Place = place,
                StartTime = itineraryItem.StartTime,
                Duration = itineraryItem.Duration,
                Note = itineraryItem.Note,
            });
        }

        [HttpPatch("{id:Guid}")]
        public async Task<ActionResult<ItineraryItemDto>> UpdateItineraryItem(Guid id, UpdateItineraryItemRequest request)
        {
            var itineraryItem = await dbContext.ItineraryItems.FindAsync(id);
            if (itineraryItem == null)
            {
                return NotFound();
            }

            Place? place = null;
            if (!string.IsNullOrEmpty(request.PlaceId))
            {
                place = await _placesCollection.Find(p => p.PlaceId == request.PlaceId).FirstOrDefaultAsync();
                if (place == null)
                {
                    return NotFound("Place not found.");
                }
            }

            itineraryItem.ItineraryDayId = request.ItineraryDayId;
            itineraryItem.PlaceId = string.IsNullOrEmpty(request.PlaceId) ? null : request.PlaceId;
            itineraryItem.StartTime = request.StartTime;
            itineraryItem.Duration = request.Duration;
            itineraryItem.Note = request.Note;
            await dbContext.SaveChangesAsync();
            
            return Ok(new ItineraryItemDto
            {
                Id = itineraryItem.Id,
                ItineraryDayId = itineraryItem.ItineraryDayId,
                Place = place,
                StartTime = itineraryItem.StartTime,
                Duration = itineraryItem.Duration,
                Note = itineraryItem.Note,
            });
        }

        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeleteItineraryItem(Guid id)
        {
            var itineraryItem = await dbContext.ItineraryItems
                .Include(i => i.ItineraryDay)
                    .ThenInclude(d => d.Plan)
                .FirstOrDefaultAsync(i => i.Id == id);
            if (itineraryItem == null)
            {
                return NotFound();
            }

            // Soft delete if plan has been synced to Google Calendar and item has a Google event
            if (itineraryItem.ItineraryDay?.Plan?.LastSyncGoogleCalendarAt != null &&
                !string.IsNullOrEmpty(itineraryItem.GoogleCalendarEventId))
            {
                itineraryItem.IsDeleted = true;
            }
            else
            {
                dbContext.ItineraryItems.Remove(itineraryItem);
            }

            await dbContext.SaveChangesAsync();
            return NoContent();
        }
    }
}