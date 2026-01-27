using dotnet.Data;
using dotnet.Dtos.Participant;
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
    public class ParticipantController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        private readonly ICurrentUser _currentUser;
        
        public ParticipantController(MySQLDbContext mySQLDbContext, ICurrentUser currentUser)
        {
            dbContext = mySQLDbContext;
            _currentUser = currentUser;
        }

        [HttpGet("{id:Guid}")]
        public async Task<ActionResult<ParticipantDto>> GetParticipantById(Guid id)
        {
            var participant = await dbContext.Participants.FindAsync(id);
            if (participant == null)
            {
                return NotFound("Participant not found.");
            }
            return Ok(new ParticipantDto
            {
                Id = participant.Id,
                UserId = participant.UserId,
                PlanId = participant.PlanId,
                Role = participant.Role,
                Status = participant.Status
            });
        }

        [HttpPost("invite")]
        public async Task<ActionResult<ParticipantDto>> SendInvitation(Guid planId, InviteTeammateRequest request)
        {
            if(request.Role == Enums.PlanRole.Owner)
            {
                return BadRequest("Cannot assign Owner role to a participant.");
            }
            var plan = await dbContext.Plans.FindAsync(planId);
            if (plan == null)
            {
                return NotFound("Plan not found.");
            }
            var user = await dbContext.Users.FindAsync(request.UserId);
            if (user == null)
            {
                return NotFound("User not found.");
            }
            var existingParticipant = await dbContext.Participants
                .Where(p => p.PlanId == planId && p.UserId == request.UserId)
                .FirstOrDefaultAsync();

            if(existingParticipant != null)
            {
                return BadRequest("User is already a participant or has a pending invitation.");
            }

            var participant = new Domains.Participant
            {
                Id = Guid.NewGuid(),
                PlanId = planId,
                UserId = request.UserId,
                Role = request.Role,
                Status = Enums.InvitationStatus.Pending
            };

            await dbContext.Participants.AddAsync(participant);
            await dbContext.SaveChangesAsync();

            return CreatedAtAction(nameof(GetParticipantById), new { id = participant.Id }, new ParticipantDto
            {
                Id = participant.Id,
                UserId = participant.UserId,
                PlanId = participant.PlanId,
                Role = participant.Role,
                Status = participant.Status
            });
        }

        [HttpPost("{id:Guid}/response")]
        public async Task<ActionResult<ParticipantDto>> RespondToInvitation(Guid id, RespondInvitationRequest request)
        {
            var participant = await dbContext.Participants.FindAsync(id);
            if (participant == null)
            {
                return NotFound("Participant not found.");
            }
            if (participant.Status != Enums.InvitationStatus.Pending)
            {
                return BadRequest("Invitation has already been responded to.");
            }

            var participantId = participant.Id;
            participant.Status = request.Status;
            await dbContext.SaveChangesAsync();
            return Ok(new ParticipantDto
            {
                Id = participant.Id,
                UserId = participant.UserId,
                PlanId = participant.PlanId,
                Role = participant.Role,
                Status = participant.Status
            });
        }

        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeleteParticipant(Guid id)
        {
            var participantToRemove = await dbContext.Participants
                .Include(p => p.Plan)
                .FirstOrDefaultAsync(p => p.Id == id);

            if (participantToRemove == null)
            {
                return NotFound("Participant not found");
            }

            if (participantToRemove.Role == Enums.PlanRole.Owner)
            {
                return BadRequest("Cannot remove plan owner");
            }

            var currentUserId = _currentUser.Id;
            if (currentUserId == null)
            {
                return Unauthorized();
            }

            if (participantToRemove.Plan.OwnerId != currentUserId && participantToRemove.UserId != currentUserId)
            {
                return Forbid("Only plan owner can remove other participants");
            }

            dbContext.Participants.Remove(participantToRemove);
            await dbContext.SaveChangesAsync();

            return NoContent();
        }
    }
}
