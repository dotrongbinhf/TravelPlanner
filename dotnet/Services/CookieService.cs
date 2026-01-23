using dotnet.Interfaces;

namespace dotnet.Services
{
    public class CookieService : ICookieService
    {

        private readonly IHttpContextAccessor _httpContextAccessor;
        private readonly IConfiguration _configuration;

        public CookieService(
            IHttpContextAccessor httpContextAccessor,
            IConfiguration configuration)
        {
            _httpContextAccessor = httpContextAccessor;
            _configuration = configuration;
        }

        public void AddRefreshTokenCookie(string refreshTokenName, string refreshToken)
        {
            var cookieOptions = new CookieOptions
            {
                HttpOnly = true,
                Secure = true,
                SameSite = SameSiteMode.Lax,
                Expires = DateTime.UtcNow.AddMinutes(_configuration.GetValue<int>("Jwt:RefreshTokenExpirationInMinutes")),
                Path = "/",
            };
            _httpContextAccessor.HttpContext?.Response.Cookies.Append(refreshTokenName, refreshToken, cookieOptions);
        }

        public string GetRefreshTokenCookie(string refreshTokenName)
        {
            return _httpContextAccessor.HttpContext?.Request.Cookies[refreshTokenName];
        }

        public void DeleteRefreshTokenCookie(string refreshTokenName)
        {
            _httpContextAccessor.HttpContext?.Response.Cookies.Delete(refreshTokenName);
        }
    }
}
