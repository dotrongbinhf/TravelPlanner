using dotnet.Dtos.ExternalApi;
using dotnet.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace dotnet.Controllers
{
    [Route("api/flight")]
    [ApiController]
    public class FlightController : ControllerBase
    {
        private readonly IExternalApiService _externalApiService;

        public FlightController(IExternalApiService externalApiService)
        {
            _externalApiService = externalApiService;
        }

        [HttpGet("search")]
        public async Task<IActionResult> SearchFlights([FromQuery] FlightSearchRequestDto request)
        {
            if (!ModelState.IsValid)
            {
                return BadRequest(ModelState);
            }

            var response = await _externalApiService.GetFlightsAsync(request);

            if (!string.IsNullOrEmpty(response.Error))
            {
                return BadRequest(response.Error);
            }

            return Ok(response);
        }

        [HttpGet("airports")]
        public async Task<IActionResult> SearchAirports([FromQuery] AirportSearchByLocationRequestDto request)
        {
            if (!ModelState.IsValid)
            {
                return BadRequest(ModelState);
            }

            var response = await _externalApiService.SearchAirportsAsync(request);

            if (!string.IsNullOrEmpty(response.Error))
            {
                return BadRequest(response.Error);
            }

            return Ok(response);
        }
    }
}
