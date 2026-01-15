using dotnet.Data;
using dotnet.Domains;
using Microsoft.AspNetCore.Mvc;
using Microsoft.IdentityModel.Tokens;
using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

namespace dotnet.Services
{
    public class AuthService
    {
        private readonly PostgreSQLDbContext dbContext;
        private readonly IConfiguration configuration;
        private readonly IHttpContextAccessor httpContextAccessor;

        public AuthService(PostgreSQLDbContext postgreSQLDbContext, IConfiguration configuration,
            IHttpContextAccessor httpContextAccessor)
        {
            dbContext = postgreSQLDbContext;
            this.configuration = configuration;
            this.httpContextAccessor = httpContextAccessor;
        }

        public string GenerateAccessToken(User user)
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            var accessTokenSecret = configuration["Jwt:AccessTokenSecret"];
            var tokenDescriptor = new SecurityTokenDescriptor
            {
                Subject = new ClaimsIdentity(new Claim[]
                {
                    new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
                    new Claim(ClaimTypes.Name, user.Username),
                    new Claim("jti", Guid.NewGuid().ToString()),
                    new Claim("iat", DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString(), ClaimValueTypes.Integer64),
                }),
                Issuer = configuration["Jwt:Issuer"],
                Audience = configuration["Jwt:Audience"],
                Expires = DateTime.UtcNow.AddMinutes(configuration.GetValue<int>("Jwt:AccessTokenExpirationInMinutes")),
                NotBefore = DateTime.UtcNow,
                SigningCredentials =
                    new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(accessTokenSecret)),
                    SecurityAlgorithms.HmacSha256Signature),
            };
            var token = tokenHandler.CreateToken(tokenDescriptor);
            return tokenHandler.WriteToken(token);
        }

        public string GenerateRefreshToken(User user)
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            var refreshTokenSecret = configuration["Jwt:RefreshTokenSecret"];
            var tokenDescriptor = new SecurityTokenDescriptor
            {
                Subject = new ClaimsIdentity(new Claim[]
                {
                    new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
                    new Claim(ClaimTypes.Name, user.Username),
                    new Claim("jti", Guid.NewGuid().ToString()),
                    new Claim("iat", DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString(), ClaimValueTypes.Integer64),
                }),
                Issuer = configuration["Jwt:Issuer"],
                Audience = configuration["Jwt:Audience"],
                Expires = DateTime.UtcNow.AddMinutes(configuration.GetValue<int>("Jwt:RefreshTokenExpirationInMinutes")),
                NotBefore = DateTime.UtcNow,
                SigningCredentials =
                    new SigningCredentials(new SymmetricSecurityKey(Encoding.UTF8.GetBytes(refreshTokenSecret)),
                    SecurityAlgorithms.HmacSha256Signature),
            };
            var token = tokenHandler.CreateToken(tokenDescriptor);
            return tokenHandler.WriteToken(token);
        }

        public bool IsTokenExpire(string token)
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

        // Add Refresh Token HttpOnly Cookie
        public void AddRefreshTokenCookie(string refreshTokenName, string refreshToken)
        {
            var cookieOptions = new CookieOptions
            {
                HttpOnly = true,
                Secure = true,
                SameSite = SameSiteMode.Lax,
                Expires = DateTime.UtcNow.AddMinutes(configuration.GetValue<int>("Jwt:RefreshTokenExpirationInMinutes")),
                Path = "/",
            };
            httpContextAccessor.HttpContext?.Response.Cookies.Append(refreshTokenName, refreshToken, cookieOptions);
        }

        // Get Refresh Token from HttpOnly Cookie
        public string GetRefreshTokenCookie(string refreshTokenName)
        {
            return httpContextAccessor.HttpContext?.Request.Cookies[refreshTokenName];
        }

        // Delete Refresh Token HttpOnly Cookie
        public void DeleteRefreshTokenCookie(string refreshTokenName)
        {
            httpContextAccessor.HttpContext?.Response.Cookies.Delete(refreshTokenName);
        }
    }
}
