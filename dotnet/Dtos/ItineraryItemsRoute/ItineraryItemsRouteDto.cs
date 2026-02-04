namespace dotnet.Dtos.ItineraryItemsRoute
{
    public class ItineraryItemsRouteDto
    {
        public Guid Id { get; set; }
        public Guid StartItineraryItemId { get; set; }
        public Guid EndItineraryItemId { get; set; }
        public List<RouteWaypointDto> Waypoints { get; set; } = new List<RouteWaypointDto>();
    }

    public class RouteWaypointDto
    {
        public Guid Id { get; set; }
        public double Lat { get; set; }
        public double Lng { get; set; }
        public int Order { get; set; }
    }
}
