using dotnet.Data;
using dotnet.Domains;
using dotnet.Dtos.Auth;
using dotnet.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Hosting;
using Microsoft.IdentityModel.Tokens;
using MongoDB.Driver;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

namespace dotnet.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class AuthController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;
        private readonly IConfiguration configuration;
        private readonly IHttpContextAccessor httpContextAccessor;
        private readonly AuthService authService;
        private readonly IMongoCollection<Place> placesCollection;
        public AuthController(MySQLDbContext mySQLDbContext, IConfiguration configuration,
            IHttpContextAccessor httpContextAccessor, AuthService authService, MongoDbService mongoDbService)
        {
            dbContext = mySQLDbContext;
            this.configuration = configuration;
            this.httpContextAccessor = httpContextAccessor;
            this.authService = authService;
            placesCollection = mongoDbService.Database.GetCollection<Place>("Place");
        }

        [HttpGet]
        [Authorize]
        public async Task<IActionResult> GetAllUser()
        {
            var users = await dbContext.Users.ToListAsync();
            //var builder = Builders<Place>.Filter;
            //var filters = new List<FilterDefinition<Place>>();
            //filters.Add(builder.Eq(doc => doc.Id, id));
            var results = await placesCollection.Find(FilterDefinition<Place>.Empty).ToListAsync();
            return Ok(results);

            //return Ok(users);
        }

        [HttpPost("login")]
        public async Task<IActionResult> Login(LoginRequest request)
        {
            if (string.IsNullOrEmpty(request.Username) || string.IsNullOrEmpty(request.Password))
            {
                return BadRequest("Missing username or password");
            }

            var user = await dbContext.Users
                    .FirstOrDefaultAsync(u => u.Username == request.Username);

            if (user == null)
            {
                return NotFound("Username doesn't exist");
            }

            if (!BCrypt.Net.BCrypt.Verify(request.Password, user.PasswordHash))
            {
                return Unauthorized("Wrong Password!");
            }

            var accessToken = authService.GenerateAccessToken(user);
            var refreshToken = authService.GenerateRefreshToken(user);

            user.RefreshToken = refreshToken;
                await dbContext.SaveChangesAsync();

            authService.AddRefreshTokenCookie("refreshToken", refreshToken);

            return Ok(new
            {
                AccessToken = accessToken,
                Username = user.Username
            });
        }

        [HttpPost("register")]
        public async Task<IActionResult> Register(RegisterRequest request)
        {
            if (string.IsNullOrEmpty(request.Username) || string.IsNullOrEmpty(request.Password))
            {
                return BadRequest("Missing username or password");
            }

            var existingUser = await dbContext.Users
                    .FirstOrDefaultAsync(u => u.Username == request.Username);

            if (existingUser != null)
            {
                return Conflict("Username already exists");
            }

            var user = new User
            {
                Id = Guid.NewGuid(),
                Username = request.Username,
                PasswordHash = BCrypt.Net.BCrypt.HashPassword(request.Password),
            };

            var accessToken = authService.GenerateAccessToken(user);
            dbContext.Users.Add(user);
            await dbContext.SaveChangesAsync();
            return Ok(new { AccessToken = accessToken });
        }

        [HttpPost("refresh-token")]
        public async Task<IActionResult> RefreshToken()
        {
            var refreshToken = authService.GetRefreshTokenCookie("refreshToken");

            if (string.IsNullOrEmpty(refreshToken))
            {
                return Ok(new
                {
                    AccessToken = ""
                });
            }

            var tokenHandler = new JwtSecurityTokenHandler();
            if (!tokenHandler.CanReadToken(refreshToken))
            {
                authService.DeleteRefreshTokenCookie("refreshToken");
                return Ok(new
                {
                    AccessToken = ""
                });
            }

            try
            {
                var tokenRead = tokenHandler.ReadJwtToken(refreshToken);
                var expClaim = tokenRead.Payload.ValidTo;
                var claimUserId = tokenRead.Payload.Claims.FirstOrDefault(c => c.Type == "nameid")?.Value;

                if (string.IsNullOrEmpty(claimUserId))
                {
                    authService.DeleteRefreshTokenCookie("refreshToken");
                    return Ok(new
                    {
                        AccessToken = ""
                    });
                }

                if (expClaim <= DateTime.UtcNow)
                {
                    authService.DeleteRefreshTokenCookie("refreshToken");
                    return Ok(new
                    {
                        AccessToken = ""
                    });
                }

                var user = await dbContext.Users.FirstOrDefaultAsync(u => u.Id.ToString() == claimUserId);
                if (user == null)
                {
                    authService.DeleteRefreshTokenCookie("refreshToken");
                    throw new ApplicationException("User not found");
                }

                if (string.IsNullOrEmpty(user.RefreshToken) || user.RefreshToken != refreshToken)
                {
                    authService.DeleteRefreshTokenCookie("refreshToken");
                    return Ok(new
                    {
                        AccessToken = ""
                    });
                }

                var newAccessToken = authService.GenerateAccessToken(user);
                return Ok(new { AccessToken = newAccessToken });
            }
            catch (Exception)
            {
                authService.DeleteRefreshTokenCookie("refreshToken");
                return Ok(new
                {
                    AccessToken = ""
                });
            }
        }

        [Authorize]
        [HttpPost("logout")]
        public async Task<IActionResult> Logout()
        {
            var refreshToken = authService.GetRefreshTokenCookie("refreshToken");
            if (string.IsNullOrEmpty(refreshToken))
            {
                return Ok("No refresh token found");
            }
            var tokenHandler = new JwtSecurityTokenHandler();
            if (!tokenHandler.CanReadToken(refreshToken))
            {
                authService.DeleteRefreshTokenCookie("refreshToken");
                return Ok("Invalid refresh token");
            }
            var tokenRead = tokenHandler.ReadJwtToken(refreshToken);
            var claimUserId = tokenRead.Payload.Claims.FirstOrDefault(c => c.Type == "nameid")?.Value;
            if (string.IsNullOrEmpty(claimUserId))
            {
                authService.DeleteRefreshTokenCookie("refreshToken");
                return Ok("Invalid refresh token");
            }
            var user = await dbContext.Users.FirstOrDefaultAsync(u => u.Id.ToString() == claimUserId);
            if (user != null)
            {
                user.RefreshToken = "";
                await dbContext.SaveChangesAsync();
            }
            authService.DeleteRefreshTokenCookie("refreshToken");
            return Ok("Logged out successfully");
        }
    }
}
