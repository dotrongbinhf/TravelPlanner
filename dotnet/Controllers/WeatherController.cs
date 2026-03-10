using dotnet.Dtos.ExternalApi;
using dotnet.Interfaces;
using Microsoft.AspNetCore.Mvc;

namespace dotnet.Controllers
{
    [Route("api/weather")]
    [ApiController]
    public class WeatherController : ControllerBase
    {
        private readonly IExternalApiService _externalApiService;

        public WeatherController(IExternalApiService externalApiService)
        {
            _externalApiService = externalApiService;
        }

        /// <summary>
        /// Get daily weather forecast (up to 16 days).
        /// Endpoint: /data/2.5/forecast/daily
        /// API Reference: https://openweathermap.org/forecast16
        /// </summary>
        [HttpGet("daily")]
        public async Task<IActionResult> GetDailyForecast([FromQuery] WeatherRequestDto request)
        {
            if (!ModelState.IsValid)
                return BadRequest(ModelState);

            if (string.IsNullOrEmpty(request.Q) && (!request.Lat.HasValue || !request.Lon.HasValue))
                return BadRequest("Either 'q' (city name) or both 'lat' and 'lon' must be provided.");

            var response = await _externalApiService.GetDailyForecastAsync(request);

            if (!string.IsNullOrEmpty(response.Error))
                return BadRequest(response.Error);

            return Ok(response);
        }
    }
}
