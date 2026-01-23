using CloudinaryDotNet.Actions;

namespace dotnet.Interfaces
{
    public interface ICloudinaryService
    {
        Task<ImageUploadResult> UploadImageAsync(IFormFile file, string publicId);
        Task<DeletionResult> DeleteImageAsync(string publicId);
    }
}
