namespace dotnet.Dtos.ItineraryItemsRoute
{
    public class UpdateItineraryItemsRouteRequest
    {
        public Guid StartItineraryItemId { get; set; }
        public Guid EndItineraryItemId { get; set; }
        public List<RouteWaypointInput> Waypoints { get; set; } = new List<RouteWaypointInput>();
    }

    public class RouteWaypointInput
    {
        public double Lat { get; set; }
        public double Lng { get; set; }
        public int Order { get; set; }
    }
}
