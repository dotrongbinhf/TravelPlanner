using dotnet.Data;
using dotnet.Domains;
using dotnet.Dtos.Plan;
using dotnet.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using MongoDB.Driver;
using System.Security.Claims;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class PlanController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        private readonly IConfiguration configuration;
        private readonly IHttpContextAccessor httpContextAccessor;
        private readonly AuthService authService;
        private readonly IMongoCollection<Place> placesCollection;
        public PlanController(MySQLDbContext mySQLDbContext, IConfiguration configuration,
            IHttpContextAccessor httpContextAccessor, AuthService authService, MongoDbService mongoDbService)
        {
            dbContext = mySQLDbContext;
            this.configuration = configuration;
            this.httpContextAccessor = httpContextAccessor;
            this.authService = authService;
            placesCollection = mongoDbService.Database.GetCollection<Place>("Place");
        }

        [HttpGet]
        public async Task<IActionResult> GetAllPlans()
        {
            var userIdString = httpContextAccessor.HttpContext.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            if(userIdString == null)
            {
                return Unauthorized();
            }
            var userId = Guid.Parse(userIdString);

            var results = await dbContext.Plans.Where(el => el.OwnerId == userId).ToListAsync();
            return Ok(results);
        }

        [HttpGet("{id:Guid}")]
        public async Task<IActionResult> GetPlanById(Guid id)
        {
            var userIdString = httpContextAccessor.HttpContext.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            if(userIdString == null)
            {
                return Unauthorized();
            }
            var userId = Guid.Parse(userIdString);

            var result = await dbContext.Plans.Where(el => el.Id == id).FirstOrDefaultAsync();
            if(result == null)
            {
                return NotFound();
            }
            return Ok(result);
        }

        [HttpPost]
        public async Task<IActionResult> CreatePlan(CreatePlanRequest request)
        {
            var userIdString = httpContextAccessor.HttpContext.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
            if(userIdString == null)
            {
                return Unauthorized();
            }
            var userId = Guid.Parse(userIdString);

            var newPlan = new Plan
            {
                Id = Guid.NewGuid(),
                OwnerId = userId,
                Name = request.Name,
                StartTime = request.StartTime,
                EndTime = request.EndTime,
                Budget = request.Budget,
                CurrencyCode = request.CurrencyCode
            };

            await dbContext.Plans.AddAsync(newPlan);
            await dbContext.SaveChangesAsync();

            return CreatedAtAction(nameof(GetPlanById), new { id = newPlan.Id }, newPlan);
        }
    }
}
