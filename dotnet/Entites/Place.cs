using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;
using System.Text.Json.Serialization;

namespace dotnet.Entites
{
    [BsonIgnoreExtraElements]
    public class Place
    {
        [BsonId]
        [BsonElement("_id"), BsonRepresentation(BsonType.ObjectId)]
        public string? Id { get; set; }
        public string PlaceId { get; set; } = string.Empty;
        public string Link { get; set; } = string.Empty; // Google Map Link
        public string Title { get; set; } = string.Empty;
        public string Category { get; set; } = string.Empty;
        public GeoJson Location { get; set; } = new GeoJson();
        public string Address { get; set; } = string.Empty;
        public OpenHours OpenHours { get; set; } = new OpenHours();
        public string Website { get; set; } = string.Empty;
        public int ReviewCount { get; set; }
        public double ReviewRating { get; set; }
        public Dictionary<int, int> ReviewsPerRating { get; set; } = new();
        public string Cid { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;
        public string Thumbnail { get; set; } = string.Empty;
        public List<Image> Images { get; set; } = new List<Image>();
        public List<UserReview> UserReviews { get; set; } = new List<UserReview>();
        public DateTime CreatedDate { get; set; }
        public DateTime ModifiedDate { get; set; }
    }

    public class GeoJson
    {
        [BsonElement("type")]
        public string Type { get; set; } = "Point";
        [BsonElement("coordinates")]
        public double[] Coordinates { get; set; } = new double[2]; // longitude first, then latitude.

        [BsonIgnore]
        [JsonIgnore]
        public double Longitude
        {
            get => Coordinates[0];
            set => Coordinates[0] = value;
        }

        [BsonIgnore]
        [JsonIgnore]
        public double Latitude
        {
            get => Coordinates[1];
            set => Coordinates[1] = value;
        }
    }

    public class OpenHours
    {
        public List<string> Monday { get; set; } = new List<string>();
        public List<string> Tuesday { get; set; } = new List<string>();
        public List<string> Wednesday { get; set; } = new List<string>();
        public List<string> Thursday { get; set; } = new List<string>();
        public List<string> Friday { get; set; } = new List<string>();
        public List<string> Saturday { get; set; } = new List<string>();
        public List<string> Sunday { get; set; } = new List<string>();
    }
    public class Image // Place Image
    {
        public string title { get; set; } = string.Empty;
        public string image { get; set; } = string.Empty;
    }

    public class UserReview
    {
        public string Name { get; set; } = string.Empty;
        public string ProfilePicture { get; set; } = string.Empty;
        public double Rating { get; set; }
        public string Description { get; set; } = string.Empty;
        public List<string> Images { get; set; } = new List<string>();
        public string When { get; set; } = string.Empty;
    }
}
