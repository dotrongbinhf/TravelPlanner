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
    }
}
