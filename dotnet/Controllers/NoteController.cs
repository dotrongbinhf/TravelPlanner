using dotnet.Data;
using dotnet.Dtos.Note;
using dotnet.Entites;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class NoteController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        public NoteController(MySQLDbContext mySQLDbContext)
        {
            dbContext = mySQLDbContext;
        }

        [HttpGet("{id:Guid}")]
        public async Task<ActionResult<NoteDto>> GetNoteById(Guid id)
        {
            var note = await dbContext.Notes.FindAsync(id);
            if (note == null)
            {
                return NotFound();
            }
            return Ok(new NoteDto
            {
                Id = note.Id,
                PlanId = note.PlanId,
                Title = note.Title,
                Content = note.Content
            });
        }

        [HttpPost()]
        public async Task<IActionResult> CreateNote(Guid planId, CreateNoteRequest request)
        {
            var plan = await dbContext.Plans.FindAsync(planId);
            if (plan == null)
            {
                return NotFound();
            }
            
            var note = new Note
            {
                Id = Guid.NewGuid(),
                PlanId = planId,
                Title = request.Title,
                Content = request.Content
            };

            await dbContext.Notes.AddAsync(note);
            await dbContext.SaveChangesAsync();

            return CreatedAtAction(nameof(GetNoteById), new { id = note.Id }, new NoteDto
            {
                Id = note.Id,
                PlanId = note.PlanId,
                Title = note.Title,
                Content = note.Content,
            });
        }

        [HttpPatch("{id:Guid}")]
        public async Task<ActionResult<NoteDto>> UpdateNote(Guid id, UpdateNoteRequest request)
        {
            var note = await dbContext.Notes.FindAsync(id);

            if (note == null)
            {
                return NotFound();
            }
            
            note.Title = request.Title;
            note.Content = request.Content;

            await dbContext.SaveChangesAsync();

            return Ok(new NoteDto
            {
                Id = note.Id,
                PlanId = note.PlanId,
                Title = note.Title,
                Content = note.Content
            });
        }

        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeleteNote(Guid id)
        {
            var note = await dbContext.Notes.FindAsync(id);
            if (note == null)
            {
                return NotFound();
            }
            dbContext.Notes.Remove(note);
            await dbContext.SaveChangesAsync();
            return NoContent();
        }
    }
}
