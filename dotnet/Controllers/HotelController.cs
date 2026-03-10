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

            return Ok(response);
        }
    }
}
