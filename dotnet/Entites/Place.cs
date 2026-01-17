using MongoDB.Bson;
using MongoDB.Bson.Serialization.Attributes;

namespace dotnet.Domains
{
    public class Place : BaseAuditableEntity
    {
        [BsonId]
        [BsonElement("_id"), BsonRepresentation(BsonType.ObjectId)]
        public string Id { get; set; } = string.Empty;
        public string PlaceId { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;
    }
}
