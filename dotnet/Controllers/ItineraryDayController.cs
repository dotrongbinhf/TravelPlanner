using dotnet.Data;
using dotnet.Dtos.ItineraryDay;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class ItineraryDayController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        public ItineraryDayController(MySQLDbContext mySQLDbContext)
        {
            dbContext = mySQLDbContext;
        }

        //[HttpGet("{id:Guid}")]
        //public async Task<ActionResult<ItineraryDayDto>> GetItineraryDayById(Guid id)
        //{
        //    var itineraryDay = await dbContext.ItineraryDays
        //        .Where(el => el.Id == id)
        //        .Include(el => el.ItineraryItems)
        //        .FirstOrDefaultAsync();
        //    if(itineraryDay == null)
        //    {
        //        return NotFound();
        //    }

        //    return new ItineraryDayDto
        //    {
        //        Id = itineraryDay.Id,
        //        PlanId = itineraryDay.PlanId,
        //        Order = itineraryDay.Order,
        //        Title = itineraryDay.Title,
        //        ItineraryItems = itineraryDay.ItineraryItems.Select(item => new Dtos.ItineraryItem.ItineraryItemDto
        //        {
        //            Id = item.Id,
        //            ItineraryDayId = item.ItineraryDayId,
        //            PlaceId = item.PlaceId,
        //            StartTime = item.StartTime,
        //            EndTime = item.EndTime,
        //        }).OrderBy(i => i.StartTime).ToList()
        //    };
        //}

        [HttpPatch("{id:Guid}")]
        public async Task<IActionResult> UpdateItineraryDay(Guid id, UpdateItineraryDayRequest request)
        {
            var itineraryDay = await dbContext.ItineraryDays.FindAsync(id);
            if (itineraryDay == null)
            {
                return NotFound();
            }
            itineraryDay.Title = request.Title ?? itineraryDay.Title;
            itineraryDay.Order = request.Order ?? itineraryDay.Order;
            await dbContext.SaveChangesAsync();
            return NoContent();
        }

        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeleteItineraryDay(Guid id)
        {
            var itineraryDay = await dbContext.ItineraryDays.FindAsync(id);
            if (itineraryDay == null)
            {
                return NotFound();
            }

            var plan = await dbContext.Plans.FindAsync(itineraryDay.PlanId);
            if (plan != null)
            {
                if (itineraryDay.Order == 0)
                {
                    plan.StartTime = plan.StartTime.AddDays(1);
                }
                else
                {
                    plan.EndTime = plan.EndTime.AddDays(-1);
                }
            }

            dbContext.ItineraryDays.Remove(itineraryDay);

            var remainingDays = await dbContext.ItineraryDays
                .Where(day => day.PlanId == itineraryDay.PlanId && day.Order > itineraryDay.Order)
                .ToListAsync();
            foreach (var day in remainingDays)
            {
                day.Order -= 1;
            }

            await dbContext.SaveChangesAsync();
            return NoContent();
        }
    }
}
