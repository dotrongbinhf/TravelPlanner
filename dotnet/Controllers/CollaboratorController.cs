using dotnet.Data;
using dotnet.Dtos.Collaborator;
using dotnet.Entites;
using dotnet.Enums;
using dotnet.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class CollaboratorController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        private readonly ICurrentUser _currentUser;
        
        public CollaboratorController(MySQLDbContext mySQLDbContext, ICurrentUser currentUser)
        {
            dbContext = mySQLDbContext;
            _currentUser = currentUser;
        }

        [HttpGet("{id:Guid}")]
        public async Task<ActionResult<CollaboratorDto>> GetCollaboratorById(Guid id)
        {
            var collaborator = await dbContext.Collaborators
                .Include(c => c.User)
                .FirstOrDefaultAsync(c => c.Id == id);
            if (collaborator == null)
            {
                return NotFound("Collaborator not found.");
            }
            return Ok(new CollaboratorDto
            {
                Id = collaborator.Id,
                UserId = collaborator.UserId,
                PlanId = collaborator.PlanId,
                Role = collaborator.Role,
                Status = collaborator.Status,
                Name = collaborator.User?.Name,
                Username = collaborator.User?.Username,
                AvatarUrl = collaborator.User?.AvatarUrl
            });
        }

        [HttpPost("invite")]
        public async Task<ActionResult<CollaboratorDto>> SendInvitation(Guid planId, InviteCollaboratorRequest request)
        {
            if(request.Role == Enums.PlanRole.Owner)
            {
                return BadRequest("Cannot assign Owner role to a collaborator.");
            }

            var currentUserId = _currentUser.Id;
            if (currentUserId == null)
            {
                return Unauthorized();
            }

            var plan = await dbContext.Plans.FindAsync(planId);
            if (plan == null)
            {
                return NotFound("Plan not found.");
            }

            // Only the owner can invite collaborators
            if (plan.OwnerId != currentUserId)
            {
                return Forbid("Only the plan owner can invite collaborators.");
            }

            var user = await dbContext.Users.FindAsync(request.UserId);
            if (user == null)
            {
                return NotFound("User not found.");
            }
            var existingCollaborator = await dbContext.Collaborators
                .Where(c => c.PlanId == planId && c.UserId == request.UserId)
                .FirstOrDefaultAsync();

            if(existingCollaborator != null)
            {
                return BadRequest("User is already a collaborator or has a pending invitation.");
            }

            var collaborator = new Collaborator
            {
                Id = Guid.NewGuid(),
                PlanId = planId,
                UserId = request.UserId,
                Role = request.Role,
                Status = InvitationStatus.Pending
            };

            await dbContext.Collaborators.AddAsync(collaborator);
            await dbContext.SaveChangesAsync();

            return CreatedAtAction(nameof(GetCollaboratorById), new { id = collaborator.Id }, new CollaboratorDto
            {
                Id = collaborator.Id,
                UserId = collaborator.UserId,
                PlanId = collaborator.PlanId,
                Role = collaborator.Role,
                Status = collaborator.Status,
                Name = user.Name,
                Username = user.Username,
                AvatarUrl = user.AvatarUrl
            });
        }

        [HttpPost("{id:Guid}/response")]
        public async Task<ActionResult<CollaboratorDto>> RespondToInvitation(Guid id, RespondInvitationRequest request)
        {
            var collaborator = await dbContext.Collaborators
                .Include(c => c.User)
                .FirstOrDefaultAsync(c => c.Id == id);
            if (collaborator == null)
            {
                return NotFound("Collaborator not found.");
            }
            if (collaborator.Status != Enums.InvitationStatus.Pending)
            {
                return BadRequest("Invitation has already been responded to.");
            }

            collaborator.Status = request.Status;
            await dbContext.SaveChangesAsync();
            return Ok(new CollaboratorDto
            {
                Id = collaborator.Id,
                UserId = collaborator.UserId,
                PlanId = collaborator.PlanId,
                Role = collaborator.Role,
                Status = collaborator.Status,
                Name = collaborator.User?.Name,
                Username = collaborator.User?.Username,
                AvatarUrl = collaborator.User?.AvatarUrl
            });
        }

        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeleteCollaborator(Guid id)
        {
            var collaboratorToRemove = await dbContext.Collaborators
                .Include(c => c.Plan)
                .FirstOrDefaultAsync(c => c.Id == id);

            if (collaboratorToRemove == null)
            {
                return NotFound("Collaborator not found");
            }

            var currentUserId = _currentUser.Id;
            if (currentUserId == null)
            {
                return Unauthorized();
            }

            if (collaboratorToRemove.Plan.OwnerId != currentUserId && collaboratorToRemove.UserId != currentUserId)
            {
                return Forbid("Only plan owner can remove other collaborators");
            }

            dbContext.Collaborators.Remove(collaboratorToRemove);
            await dbContext.SaveChangesAsync();

            return NoContent();
        }
    }
}
