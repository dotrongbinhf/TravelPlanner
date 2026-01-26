using dotnet.Data;
using dotnet.Domains;
using dotnet.Dtos.Auth;
using dotnet.Interfaces;
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
        private readonly IMongoCollection<Place> _placesCollection;
        private readonly ICurrentUser _currentUser;
        private readonly ICookieService _cookieService;
        private readonly IConfiguration _configuration;

        public AuthController(MySQLDbContext mySQLDbContext, MongoDbService mongoDbService,
            ICurrentUser currentUser, ICookieService cookieService,
            IConfiguration configuration)
        {
            dbContext = mySQLDbContext;
            _placesCollection = mongoDbService.Database.GetCollection<Place>("Place");
            _currentUser = currentUser;
            _cookieService = cookieService;
            _configuration = configuration;
        }

        [HttpGet]
        [Authorize]
        public async Task<IActionResult> GetAllUser()
        {
            var users = await dbContext.Users.ToListAsync();
            //var builder = Builders<Place>.Filter;
            //var filters = new List<FilterDefinition<Place>>();
            //filters.Add(builder.Eq(doc => doc.Id, id));
            var results = await _placesCollection.Find(FilterDefinition<Place>.Empty).ToListAsync();
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
                return BadRequest("Wrong Password!");
            }

            var accessToken = GenerateAccessToken(user);
            var refreshToken = GenerateRefreshToken(user);

            user.RefreshToken = refreshToken;
                await dbContext.SaveChangesAsync();

            _cookieService.AddRefreshTokenCookie("refreshToken", refreshToken);

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

            var accessToken = GenerateAccessToken(user);
            dbContext.Users.Add(user);
            await dbContext.SaveChangesAsync();
            return Ok(new { AccessToken = accessToken });
        }

        [HttpPost("refresh-token")]
        public async Task<IActionResult> RefreshToken()
        {
            var refreshToken = _cookieService.GetRefreshTokenCookie("refreshToken");

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
                _cookieService.DeleteRefreshTokenCookie("refreshToken");
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
                    _cookieService.DeleteRefreshTokenCookie("refreshToken");
                    return Ok(new
                    {
                        AccessToken = ""
                    });
                }

                if (expClaim <= DateTime.UtcNow)
                {
                    _cookieService.DeleteRefreshTokenCookie("refreshToken");
                    return Ok(new
                    {
                        AccessToken = ""
                    });
                }

                var user = await dbContext.Users.FirstOrDefaultAsync(u => u.Id.ToString() == claimUserId);
                if (user == null)
                {
                    _cookieService.DeleteRefreshTokenCookie("refreshToken");
                    throw new ApplicationException("User not found");
                }

                if (string.IsNullOrEmpty(user.RefreshToken) || user.RefreshToken != refreshToken)
                {
                    _cookieService.DeleteRefreshTokenCookie("refreshToken");
                    return Ok(new
                    {
                        AccessToken = ""
                    });
                }

                var newAccessToken = GenerateAccessToken(user);
                return Ok(new { AccessToken = newAccessToken });
            }
            catch (Exception)
            {
                _cookieService.DeleteRefreshTokenCookie("refreshToken");
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
            var refreshToken = _cookieService.GetRefreshTokenCookie("refreshToken");
            if (string.IsNullOrEmpty(refreshToken))
            {
                return Ok("No refresh token found");
            }
            var tokenHandler = new JwtSecurityTokenHandler();
            if (!tokenHandler.CanReadToken(refreshToken))
            {
                _cookieService.DeleteRefreshTokenCookie("refreshToken");
                return Ok("Invalid refresh token");
            }
            var tokenRead = tokenHandler.ReadJwtToken(refreshToken);
            var claimUserId = tokenRead.Payload.Claims.FirstOrDefault(c => c.Type == "nameid")?.Value;
            if (string.IsNullOrEmpty(claimUserId))
            {
                _cookieService.DeleteRefreshTokenCookie("refreshToken");
                return Ok("Invalid refresh token");
            }
            var user = await dbContext.Users.FirstOrDefaultAsync(u => u.Id.ToString() == claimUserId);
            if (user != null)
            {
                user.RefreshToken = "";
                await dbContext.SaveChangesAsync();
            }
            _cookieService.DeleteRefreshTokenCookie("refreshToken");
            return Ok("Logged out successfully");
        }

        #region Private Methods
        private string GenerateAccessToken(User user)
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            var accessTokenSecret = _configuration["Jwt:AccessTokenSecret"];
            var tokenDescriptor = new SecurityTokenDescriptor
            {
                Subject = new ClaimsIdentity(new Claim[]
                {
                    new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
                    new Claim(ClaimTypes.Name, user.Username),
                    new Claim("jti", Guid.NewGuid().ToString()),
                    new Claim("iat", DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString(), ClaimValueTypes.Integer64),
                }),
                Issuer = _configuration["Jwt:Issuer"],
                Audience = _configuration["Jwt:Audience"],
                Expires = DateTime.UtcNow.AddMinutes(_configuration.GetValue<int>("Jwt:AccessTokenExpirationInMinutes")),
                NotBefore = DateTime.UtcNow,
                SigningCredentials =
                    new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(accessTokenSecret)),
                    SecurityAlgorithms.HmacSha256Signature),
            };
            var token = tokenHandler.CreateToken(tokenDescriptor);
            return tokenHandler.WriteToken(token);
        }

        private string GenerateRefreshToken(User user)
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            var refreshTokenSecret = _configuration["Jwt:RefreshTokenSecret"];
            var tokenDescriptor = new SecurityTokenDescriptor
            {
                Subject = new ClaimsIdentity(new Claim[]
                {
                    new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
                    new Claim(ClaimTypes.Name, user.Username),
                    new Claim("jti", Guid.NewGuid().ToString()),
                    new Claim("iat", DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString(), ClaimValueTypes.Integer64),
                }),
                Issuer = _configuration["Jwt:Issuer"],
                Audience = _configuration["Jwt:Audience"],
                Expires = DateTime.UtcNow.AddMinutes(_configuration.GetValue<int>("Jwt:RefreshTokenExpirationInMinutes")),
                NotBefore = DateTime.UtcNow,
                SigningCredentials =
                    new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(refreshTokenSecret)),
                    SecurityAlgorithms.HmacSha256Signature),
            };
            var token = tokenHandler.CreateToken(tokenDescriptor);
            return tokenHandler.WriteToken(token);
        }

        private bool IsTokenExpire(string token)
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            if (tokenHandler.CanReadToken(token))
            {
                var tokenRead = tokenHandler.ReadJwtToken(token);
                var expClaim = tokenRead.Payload.Expiration;

                if (expClaim.HasValue)
                {
                    var expirationTime = DateTimeOffset.FromUnixTimeSeconds(expClaim.Value).UtcDateTime;
                    if (expirationTime < DateTime.UtcNow)
                    {
                        return true;
                    }

                    return false;
                }
            }

            return true;
        }

        #endregion
    }
}
