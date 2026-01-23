using Microsoft.AspNetCore.Http;

namespace dotnet.Interfaces
{
    public interface ICookieService
    {
        void AddRefreshTokenCookie(string refreshTokenName, string refreshToken);
        string GetRefreshTokenCookie(string refreshTokenName);
        void DeleteRefreshTokenCookie(string refreshTokenName);
    }
}
