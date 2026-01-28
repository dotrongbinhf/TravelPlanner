using dotnet.Data;
using dotnet.Entites;
using dotnet.Dtos.ExpenseItem;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class ExpenseItemController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        public ExpenseItemController(MySQLDbContext mySQLDbContext)
        {
            dbContext = mySQLDbContext;
        }

        [HttpGet("{id:Guid}")]
        public async Task<ActionResult<ExpenseItemDto>> GetExpenseItemById(Guid id)
        {
            var expenseItem = await dbContext.ExpenseItems.FindAsync(id);
            if (expenseItem == null) return NotFound();

            return Ok(new ExpenseItemDto
            {
                Id = expenseItem.Id,
                PlanId = expenseItem.PlanId,
                Category = expenseItem.Category,
                Name = expenseItem.Name,
                Amount = expenseItem.Amount
            });
        }

        [HttpPost]
        public async Task<IActionResult> CreateExpenseItem(Guid planId, CreateExpenseItemRequest request)
        {
            var plan = await dbContext.Plans.FindAsync(planId);
            if (plan == null) return NotFound();

            var expenseItem = new ExpenseItem
            {
                Id = Guid.NewGuid(),
                PlanId = planId,
                Category = request.Category,
                Name = request.Name,
                Amount = request.Amount
            };

            dbContext.ExpenseItems.Add(expenseItem);
            await dbContext.SaveChangesAsync();

            return CreatedAtAction(nameof(GetExpenseItemById), new { id = expenseItem.Id }, new ExpenseItemDto
            {
                Id = expenseItem.Id,
                PlanId = expenseItem.PlanId,
                Category = expenseItem.Category,
                Name = expenseItem.Name,
                Amount = expenseItem.Amount
            });
        }

        [HttpPatch("{id:Guid}")]
        public async Task<ActionResult<ExpenseItemDto>> UpdateExpenseItem(Guid id, UpdateExpenseItemRequest request)
        {
            var expenseItem = await dbContext.ExpenseItems.FindAsync(id);
            if (expenseItem == null) return NotFound();

            expenseItem.Category = request.Category;
            expenseItem.Name = request.Name;
            expenseItem.Amount = request.Amount;

            await dbContext.SaveChangesAsync();

            return Ok(new ExpenseItemDto
            {
                Id = expenseItem.Id,
                PlanId = expenseItem.PlanId,
                Category = expenseItem.Category,
                Name = expenseItem.Name,
                Amount = expenseItem.Amount
            });
        }

        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeleteExpenseItem(Guid id)
        {
            var expenseItem = await dbContext.ExpenseItems.FindAsync(id);
            if(expenseItem == null) return NotFound();

            dbContext.ExpenseItems.Remove(expenseItem);
            await dbContext.SaveChangesAsync();
            return NoContent();
        }
    }
}
