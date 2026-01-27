using dotnet.Dtos.User;

namespace dotnet.Dtos.Auth
{
    public class RegisterResponse
    {
        public string AccessToken { get; set; } = string.Empty;
        public UserDto User { get; set; } = new UserDto();
    }
}
