using dotnet.Data;
using dotnet.Dtos.User;
using dotnet.Interfaces;
using dotnet.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class UserController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        private readonly ICurrentUser _currentUser;
        private readonly ICloudinaryService _cloudinaryService;

        public UserController(MySQLDbContext mySQLDbContext, ICurrentUser currentUser, ICloudinaryService cloudinaryService)
        {
            dbContext = mySQLDbContext;
            _currentUser = currentUser;
            _cloudinaryService = cloudinaryService;
        }

        [HttpGet("me")]
        public async Task<ActionResult<UserDto>> GetMe()
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }
            var user = await dbContext.Users.FindAsync(userId);
            if (user == null)
            {
                return NotFound();
            }
            var userDto = new UserDto
            {
                Id = user.Id,
                Username = user.Username,
                Name = user.Name,
                AvatarUrl = user.AvatarUrl,
                Email = user.Email
            };
            return Ok(userDto);
        }

        [HttpPatch("me")]
        public async Task<ActionResult<UserDto>> UpdateUserInformation(UpdateUserRequest request)
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }
            var user = await dbContext.Users.FindAsync(userId);
            if (user == null)
            {
                return NotFound();
            }
            user.Name = request.Name ?? user.Name;
            user.Email = request.Email ?? user.Email;
            await dbContext.SaveChangesAsync();
            var userDto = new UserDto
            {
                Id = user.Id,
                Username = user.Username,
                Name = user.Name,
                AvatarUrl = user.AvatarUrl,
                Email = user.Email
            };
            return Ok(userDto);
        }

        [HttpPost("me/change-password")]
        public async Task<IActionResult> ChangePassword(ChangePasswordRequest request)
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }
            var user = await dbContext.Users.FindAsync(userId);
            if (user == null)
            {
                return NotFound();
            }
            if (!BCrypt.Net.BCrypt.Verify(request.CurrentPassword, user.PasswordHash))
            {
                return Unauthorized("Wrong Current Password!");
            }
            user.PasswordHash = BCrypt.Net.BCrypt.HashPassword(request.NewPassword);
            await dbContext.SaveChangesAsync();

            return NoContent();
        }

        [HttpPatch("me/avatar")]
        public async Task<IActionResult> UploadAvatar(IFormFile avatar)
        {
            var userId = _currentUser.Id;
            if (userId == null)
            {
                return Unauthorized();
            }
            var user = await dbContext.Users.FindAsync(userId);
            if (user == null)
            {
                return NotFound();
            }

            var uploadResult = await _cloudinaryService.UploadImageAsync(avatar, userId.ToString(), "Users_Avatar");
            if (uploadResult.Error != null)
            {
                return BadRequest(uploadResult.Error.Message);
            }
            user.AvatarUrl = uploadResult.SecureUrl.ToString();
            await dbContext.SaveChangesAsync();
            return Ok(new { AvatarUrl = user.AvatarUrl });
        }
    }
}
