namespace dotnet.Entites
{
    public class RouteWaypoint : BaseAuditableEntity
    {
        public Guid Id { get; set; }
        public Guid ItineraryItemsRouteId { get; set; }
        public double Lat { get; set; }
        public double Lng { get; set; }
        public int Order { get; set; }

        public ItineraryItemsRoute ItineraryItemsRoute { get; set; }
    }
}
