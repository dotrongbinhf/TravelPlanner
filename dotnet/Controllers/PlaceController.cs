using dotnet.Data;
using dotnet.Entites;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using MongoDB.Driver;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class PlaceController : ControllerBase
    {
        private readonly IMongoCollection<Place> _placesCollection;
        public PlaceController(MongoDbService mongoDbService)
        {
            _placesCollection = mongoDbService.Database.GetCollection<Place>("Place");
        }

        [HttpGet("{id}")]
        public async Task<ActionResult<Place>> GetPlaceById(string id)
        {
            var place = await _placesCollection.Find(p => p.PlaceId == id).FirstOrDefaultAsync();
            if (place == null)
            {
                return NotFound();
            }
            return place;
        }

        [HttpPost]
        public async Task<ActionResult<Place>> CreatePlace(Place newPlace)
        {
            newPlace.CreatedDate = DateTime.UtcNow;
            newPlace.ModifiedDate = DateTime.UtcNow;
            newPlace.Id = null;
            var isPlaceExisting = await _placesCollection
                .Find(p => p.PlaceId == newPlace.PlaceId)
                .FirstOrDefaultAsync();
            if (isPlaceExisting != null)
            {
                return Conflict("Place with the same PlaceId already exists.");
            }

            await _placesCollection.InsertOneAsync(newPlace);
            return CreatedAtAction(nameof(GetPlaceById), new { id = newPlace.PlaceId }, newPlace);
        }
    }
}
