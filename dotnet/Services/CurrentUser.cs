using dotnet.Interfaces;
using Microsoft.AspNetCore.Http;
using System.Security.Claims;

namespace dotnet.Services
{
    public class CurrentUser : ICurrentUser
    {
        private readonly IHttpContextAccessor _httpContextAccessor;

        public CurrentUser(IHttpContextAccessor httpContextAccessor)
        {
            _httpContextAccessor = httpContextAccessor;
        }

        public Guid? Id
        {
            get
            {
                var userIdString = _httpContextAccessor.HttpContext?.User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
                if (Guid.TryParse(userIdString, out var userId))
                {
                    return userId;
                }
                return null;
            }
        }
    }
}
