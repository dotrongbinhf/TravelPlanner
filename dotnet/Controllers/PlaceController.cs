using dotnet.Data;
using dotnet.Entites;
using dotnet.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using MongoDB.Driver;

namespace dotnet.Controllers
{
    [ApiController]
    //[Authorize]
    [Route("api/[controller]")]
    public class PlaceController : ControllerBase
    {
        private readonly IMongoCollection<Place> _placesCollection;
        private readonly IExternalApiService _externalApiService;
        public PlaceController(MongoDbService mongoDbService, IExternalApiService externalApiService)
        {
            _placesCollection = mongoDbService.Database.GetCollection<Place>("Place");
            _externalApiService = externalApiService;
        }

        [HttpGet("{id}")]
        public async Task<ActionResult<Place>> GetPlaceById(string id)
        {
            // Step 1: Look up in DB
            var place = await _placesCollection.Find(p => p.PlaceId == id).FirstOrDefaultAsync();
            if (place != null)
            {
                return place;
            }

            // Step 2: Not found → fetch from Google Places API and save
            var googlePlace = await _externalApiService.GetPlaceDetailsAsync(id);
            if (googlePlace == null)
            {
                return NotFound($"Place not found in DB and could not fetch from Google Places API: {id}");
            }

            // Check for race condition
            var existing = await _placesCollection.Find(p => p.PlaceId == id).FirstOrDefaultAsync();
            if (existing != null)
            {
                return existing;
            }

            googlePlace.Id = null; // Let MongoDB generate the Id
            await _placesCollection.InsertOneAsync(googlePlace);
            return CreatedAtAction(nameof(GetPlaceById), new { id = googlePlace.PlaceId }, googlePlace);
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
