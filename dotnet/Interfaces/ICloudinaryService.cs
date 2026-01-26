using CloudinaryDotNet.Actions;

namespace dotnet.Interfaces
{
    public interface ICloudinaryService
    {
        Task<ImageUploadResult> UploadImageAsync(IFormFile file, string publicId, string folderName);
        Task<DeletionResult> DeleteImageAsync(string publicId);
    }
}
