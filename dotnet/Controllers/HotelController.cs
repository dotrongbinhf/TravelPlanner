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

            // Trim: keep only Properties (max 10), flatten rates, remove tokens/links
            var trimmedProperties = (response.Properties ?? new())
                .Take(10)
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
                    p.OverallRating,
                    p.Reviews,
                    p.LocationRating,
                    p.ReviewsBreakdown,
                });

            return Ok(new { Properties = trimmedProperties });
        }
    }
}
