using dotnet.Data;
using dotnet.Dtos.ItineraryItem;
using dotnet.Entites;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
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

            var place = await _placesCollection.Find(p => p.PlaceId == itineraryItem.PlaceId).FirstOrDefaultAsync();

            return Ok(new ItineraryItemDto
            {
                Id = itineraryItem.Id,
                ItineraryDayId = itineraryItem.ItineraryDayId,
                Place = place,
                StartTime = itineraryItem.StartTime,
                Duration = itineraryItem.Duration,
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

            var place = await _placesCollection.Find(p => p.PlaceId == request.PlaceId).FirstOrDefaultAsync();
            if (place == null)
            {
                return NotFound();
            }

            var itineraryItem = new ItineraryItem
            {
                Id = Guid.NewGuid(),
                ItineraryDayId = itineraryDayId,
                PlaceId = request.PlaceId,
                StartTime = request.StartTime,
                Duration = request.Duration
            };

            dbContext.ItineraryItems.Add(itineraryItem);
            await dbContext.SaveChangesAsync();

            return CreatedAtAction(nameof(GetItineraryItemById), new { id = itineraryItem.Id }, new ItineraryItemDto
            {
                Id = itineraryItem.Id,
                ItineraryDayId = itineraryItem.ItineraryDayId,
                Place = place,
                StartTime = itineraryItem.StartTime,
                Duration = itineraryItem.Duration
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
            var place = await _placesCollection.Find(p => p.PlaceId == itineraryItem.PlaceId).FirstOrDefaultAsync();
            if (place == null)
            {
                return NotFound();
            }

            itineraryItem.ItineraryDayId = request.ItineraryDayId;
            itineraryItem.StartTime = request.StartTime;
            itineraryItem.Duration = request.Duration;
            await dbContext.SaveChangesAsync();
            return Ok(new ItineraryItemDto
            {
                Id = itineraryItem.Id,
                ItineraryDayId = itineraryItem.ItineraryDayId,
                Place = place,
                StartTime = itineraryItem.StartTime,
                Duration = itineraryItem.Duration
            });
        }

        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeleteItineraryItem(Guid id)
        {
            var itineraryItem = await dbContext.ItineraryItems.FindAsync(id);
            if (itineraryItem == null)
            {
                return NotFound();
            }
            dbContext.ItineraryItems.Remove(itineraryItem);
            await dbContext.SaveChangesAsync();
            return NoContent();
        }
    }
}