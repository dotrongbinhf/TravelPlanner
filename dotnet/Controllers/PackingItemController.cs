using dotnet.Data;
using dotnet.Dtos.PackingItem;
using dotnet.Entites;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class PackingItemController: ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        public PackingItemController(MySQLDbContext mySQLDbContext)
        {
            dbContext = mySQLDbContext;
        }

        [HttpGet("{id:Guid}")]
        public async Task<ActionResult<PackingItemDto>> GetPackingItemById(Guid id)
        {
            var packingItem = await dbContext.PackingItems.FindAsync(id);

            if (packingItem == null)
            {
                return NotFound();
            }
            return Ok(new PackingItemDto
            {
                Id = packingItem.Id,
                PackingListId = packingItem.PackingListId,
                Name = packingItem.Name,
                IsPacked = packingItem.IsPacked
            });
        }

        [HttpPost]
        public async Task<ActionResult<PackingItemDto>> CreatePackingItem(Guid packingListId, CreatePackingItemRequest request)
        {
            var packingList = await dbContext.PackingLists.FindAsync(packingListId);
            if (packingList == null)
            {
                return NotFound();
            }
            var packingItem = new PackingItem
            {
                Id = Guid.NewGuid(),
                PackingListId = packingListId,
                Name = request.Name,
                IsPacked = false
            };
            await dbContext.PackingItems.AddAsync(packingItem);
            await dbContext.SaveChangesAsync();
            return CreatedAtAction(nameof(GetPackingItemById), new { id = packingItem.Id }, new PackingItemDto
            {
                Id = packingItem.Id,
                PackingListId = packingItem.PackingListId,
                Name = packingItem.Name,
                IsPacked = packingItem.IsPacked
            });
        }

        [HttpPatch("{id:Guid}")]
        public async Task<ActionResult<PackingItemDto>> UpdatePackingItem(Guid id, UpdatePackingItemRequest request)
        {
            var packingItem = await dbContext.PackingItems.FindAsync(id);
            if (packingItem == null)
            {
                return NotFound();
            }
            packingItem.Name = request.Name ?? packingItem.Name;
            if (request.IsPacked.HasValue)
            {
                packingItem.IsPacked = request.IsPacked.Value;
            }
            await dbContext.SaveChangesAsync();
            return Ok(new PackingItemDto
            {
                Id = packingItem.Id,
                PackingListId = packingItem.PackingListId,
                Name = packingItem.Name,
                IsPacked = packingItem.IsPacked
            });
        }

        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeletePackingItem(Guid id)
        {
            var packingItem = await dbContext.PackingItems.FindAsync(id);
            if (packingItem == null)
            {
                return NotFound();
            }
            dbContext.PackingItems.Remove(packingItem);
            await dbContext.SaveChangesAsync();
            return NoContent();
        }
    }
}
