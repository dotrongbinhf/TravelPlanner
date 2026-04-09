using dotnet.Dtos.ExternalApi;
using dotnet.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace dotnet.Controllers
{
    [Route("api/hotel")]
    [ApiController]
    public class HotelController : ControllerBase
    {
        private readonly IExternalApiService _externalApiService;

        public HotelController(IExternalApiService externalApiService)
        {
            _externalApiService = externalApiService;
        }

        [HttpGet("search")]
        public async Task<IActionResult> GetHotels([FromQuery] HotelSearchRequestDto request)
        {
            if (!ModelState.IsValid)
            {
                return BadRequest(ModelState);
            }

            var response = await _externalApiService.GetHotelsAsync(request);
            
            if (!string.IsNullOrEmpty(response.Error))
            {
                return BadRequest(response.Error);
            }

            var trimmedProperties = (response.Properties ?? new())
                .Take(5)
                .Select(p => new
                {
                    p.Type,
                    p.Name,
                    p.Link,
                    p.GpsCoordinates,
                    p.CheckInTime,
                    p.CheckOutTime,
                    RatePerNight = p.RatePerNight?.Lowest,
                    TotalRate = p.TotalRate?.Lowest,
                    p.NearbyPlaces,
                    p.HotelClass,
                    p.OverallRating,
                    p.Reviews,
                    p.LocationRating,
                    p.ReviewsBreakdown,
                    p.Amenities,
                });

            return Ok(new { Properties = trimmedProperties });
        }
    }
}
