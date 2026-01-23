using dotnet.Data;
using dotnet.Dtos.PackingList;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class PackingListController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        public PackingListController(MySQLDbContext dbContext)
        {
            this.dbContext = dbContext;
        }

        [HttpGet("{id:Guid}")]
        public async Task<ActionResult<PackingListDto>> GetPackingListById(Guid id)
        {
            var packingList = await dbContext.PackingLists
                .Where(el => el.Id == id)
                .Include(el => el.PackingItems)
                .FirstOrDefaultAsync();

            if (packingList == null)
            {
                return NotFound();
            }
            return Ok(new PackingListDto
            {
                Id = packingList.Id,
                PlanId = packingList.PlanId,
                Name = packingList.Name,
                PackingItems = packingList.PackingItems.Select(item => new Dtos.PackingItem.PackingItemDto
                {
                    Id = item.Id,
                    PackingListId = item.PackingListId,
                    Name = item.Name,
                    IsPacked = item.IsPacked
                }).ToList()
            });
        }

        [HttpPost]
        public async Task<IActionResult> CreatePackingList(Guid planId, CreatePackingListRequest request)
        {
            var plan = await dbContext.Plans.FindAsync(planId);
            if (plan == null)
            {
                return NotFound();
            }
            var packingList = new Domains.PackingList
            {
                Id = Guid.NewGuid(),
                PlanId = planId,
                Name = request.Name
            };
            await dbContext.PackingLists.AddAsync(packingList);
            await dbContext.SaveChangesAsync();
            return CreatedAtAction(nameof(GetPackingListById), new { id = packingList.Id }, new PackingListDto
            {
                Id = packingList.Id,
                PlanId = packingList.PlanId,
                Name = packingList.Name,
                PackingItems = new List<Dtos.PackingItem.PackingItemDto>()
            });
        }

        [HttpPatch("{id:Guid}")]
        public async Task<ActionResult<PackingListDto>> UpdatePackingList(Guid id, UpdatePackingListRequest request)
        {
            var packingList = await dbContext.PackingLists.FindAsync(id);
            if (packingList == null)
            {
                return NotFound();
            }
            packingList.Name = request.Name;
            await dbContext.SaveChangesAsync();
            return Ok(new PackingListDto
            {
                Id = packingList.Id,
                PlanId = packingList.PlanId,
                Name = packingList.Name,
                PackingItems = packingList.PackingItems.Select(item => new Dtos.PackingItem.PackingItemDto
                {
                    Id = item.Id,
                    PackingListId = item.PackingListId,
                    Name = item.Name,
                    IsPacked = item.IsPacked
                }).ToList()
            });
        }

        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeletePackingList(Guid id)
        {
            var packingList = await dbContext.PackingLists.FindAsync(id);
            if (packingList == null)
            {
                return NotFound();
            }
            dbContext.PackingLists.Remove(packingList);
            await dbContext.SaveChangesAsync();
            return NoContent();
        }
    }
}
