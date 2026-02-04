namespace dotnet.Entites
{
    public class ItineraryItemsRoute : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid StartItineraryItemId { get; set; }
        public Guid EndItineraryItemId { get; set; }

        public ItineraryItem StartItineraryItem { get; set; }
        public ItineraryItem EndItineraryItem { get; set; }
        public ICollection<RouteWaypoint> Waypoints { get; set; } = new List<RouteWaypoint>(); // RouteWaypoints -> Later Update
    }
}
