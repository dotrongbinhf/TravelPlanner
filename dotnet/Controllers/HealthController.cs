using Microsoft.AspNetCore.Mvc;

namespace dotnet.Controllers
{
    [ApiController]
    [Route("[controller]")]
    public class HealthController : ControllerBase
    {
        private readonly ILogger<HealthController> _logger;

        public HealthController(ILogger<HealthController> logger)
        {
            _logger = logger;
        }

        [HttpGet]
        public IActionResult Get()
        {
            return Ok("Healthy From .NET");
        }

        [HttpGet("fastapi")]
        public IActionResult GetFastApiHealth()
        {
            const string fastApiHealthUrl = "http://localhost:8000/health/circle";
            using var httpClient = new HttpClient();
            var response = httpClient.GetAsync(fastApiHealthUrl).Result;

            var content = response.Content.ReadAsStringAsync().Result;
            return Ok(new { status = "Healthy", fastApiStatus = content });
        }
    }
}
