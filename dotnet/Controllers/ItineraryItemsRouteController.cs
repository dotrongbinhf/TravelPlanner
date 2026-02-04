using dotnet.Data;
using dotnet.Dtos.ItineraryItemsRoute;
using dotnet.Entites;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace dotnet.Controllers
{
    [ApiController]
    [Authorize]
    [Route("api/[controller]")]
    public class ItineraryItemsRouteController : ControllerBase
    {
        private readonly MySQLDbContext dbContext;

        public ItineraryItemsRouteController(MySQLDbContext mySQLDbContext)
        {
            dbContext = mySQLDbContext;
        }

        /// <summary>
        /// Get all routes for items in a specific itinerary day
        /// </summary>
        [HttpGet("day/{dayId:Guid}")]
        public async Task<ActionResult<List<ItineraryItemsRouteDto>>> GetRoutesByDayId(Guid dayId)
        {
            // Get all itinerary items for this day
            var itemIds = await dbContext.ItineraryItems
                .Where(item => item.ItineraryDayId == dayId)
                .Select(item => item.Id)
                .ToListAsync();

            if (!itemIds.Any())
            {
                return Ok(new List<ItineraryItemsRouteDto>());
            }

            // Get all routes where both start and end items are in this day
            var routes = await dbContext.ItineraryItemsRoutes
                .Where(route => itemIds.Contains(route.StartItineraryItemId) && itemIds.Contains(route.EndItineraryItemId))
                .Include(route => route.Waypoints.OrderBy(w => w.Order))
                .ToListAsync();

            var routeDtos = routes.Select(route => new ItineraryItemsRouteDto
            {
                Id = route.Id,
                StartItineraryItemId = route.StartItineraryItemId,
                EndItineraryItemId = route.EndItineraryItemId,
                Waypoints = route.Waypoints.Select(w => new RouteWaypointDto
                {
                    Id = w.Id,
                    Lat = w.Lat,
                    Lng = w.Lng,
                    Order = w.Order
                }).ToList()
            }).ToList();

            return Ok(routeDtos);
        }

        /// <summary>
        /// Get route for specific start and end itinerary items
        /// Current use for route between last item of one day and first item of next day
        /// </summary>
        [HttpGet("between/{startItemId:Guid}/{endItemId:Guid}")]
        public async Task<ActionResult<ItineraryItemsRouteDto>> GetRouteBetweenItems(Guid startItemId, Guid endItemId)
        {
            var route = await dbContext.ItineraryItemsRoutes
                .Include(r => r.Waypoints.OrderBy(w => w.Order))
                .FirstOrDefaultAsync(r =>
                    r.StartItineraryItemId == startItemId &&
                    r.EndItineraryItemId == endItemId);

            if (route == null)
            {
                return NotFound("Route not found");
            }

            var routeDto = new ItineraryItemsRouteDto
            {
                Id = route.Id,
                StartItineraryItemId = route.StartItineraryItemId,
                EndItineraryItemId = route.EndItineraryItemId,
                Waypoints = route.Waypoints.Select(w => new RouteWaypointDto
                {
                    Id = w.Id,
                    Lat = w.Lat,
                    Lng = w.Lng,
                    Order = w.Order
                }).ToList()
            };

            return Ok(routeDto);
        }

        /// <summary>
        /// Upsert route with waypoints (create or update based on start+end item IDs)
        /// Direction Service return Waypoints and order after waypoint changes so it is easier to just replace all waypoints on update
        /// </summary>
        [HttpPut]
        public async Task<ActionResult<ItineraryItemsRouteDto>> UpsertRoute(UpdateItineraryItemsRouteRequest request)
        {
            // Validate that both items exist
            var startItem = await dbContext.ItineraryItems.FindAsync(request.StartItineraryItemId);
            var endItem = await dbContext.ItineraryItems.FindAsync(request.EndItineraryItemId);

            if (startItem == null || endItem == null)
            {
                return NotFound("One or both itinerary items not found");
            }

            // Find existing route (without tracking waypoints to avoid concurrency issues)
            var existingRoute = await dbContext.ItineraryItemsRoutes
                .AsNoTracking()
                .FirstOrDefaultAsync(r =>
                    r.StartItineraryItemId == request.StartItineraryItemId &&
                    r.EndItineraryItemId == request.EndItineraryItemId);

            if (existingRoute != null)
            {
                // Delete existing waypoints using ExecuteDeleteAsync to avoid tracking conflicts
                await dbContext.RouteWaypoints
                    .Where(w => w.ItineraryItemsRouteId == existingRoute.Id)
                    .ExecuteDeleteAsync();

                // Add new waypoints
                var newWaypoints = request.Waypoints.Select(w => new RouteWaypoint
                {
                    Id = Guid.NewGuid(),
                    ItineraryItemsRouteId = existingRoute.Id,
                    Lat = w.Lat,
                    Lng = w.Lng,
                    Order = w.Order
                }).ToList();

                dbContext.RouteWaypoints.AddRange(newWaypoints);
                await dbContext.SaveChangesAsync();

                return Ok(new ItineraryItemsRouteDto
                {
                    Id = existingRoute.Id,
                    StartItineraryItemId = existingRoute.StartItineraryItemId,
                    EndItineraryItemId = existingRoute.EndItineraryItemId,
                    Waypoints = newWaypoints.Select(w => new RouteWaypointDto
                    {
                        Id = w.Id,
                        Lat = w.Lat,
                        Lng = w.Lng,
                        Order = w.Order
                    }).ToList()
                });
            }
            else
            {
                // Create new route
                var newRoute = new ItineraryItemsRoute
                {
                    Id = Guid.NewGuid(),
                    StartItineraryItemId = request.StartItineraryItemId,
                    EndItineraryItemId = request.EndItineraryItemId,
                    Waypoints = request.Waypoints.Select(w => new RouteWaypoint
                    {
                        Id = Guid.NewGuid(),
                        Lat = w.Lat,
                        Lng = w.Lng,
                        Order = w.Order
                    }).ToList()
                };

                dbContext.ItineraryItemsRoutes.Add(newRoute);
                await dbContext.SaveChangesAsync();

                return CreatedAtAction(nameof(GetRoutesByDayId), new { dayId = startItem.ItineraryDayId }, new ItineraryItemsRouteDto
                {
                    Id = newRoute.Id,
                    StartItineraryItemId = newRoute.StartItineraryItemId,
                    EndItineraryItemId = newRoute.EndItineraryItemId,
                    Waypoints = newRoute.Waypoints.Select(w => new RouteWaypointDto
                    {
                        Id = w.Id,
                        Lat = w.Lat,
                        Lng = w.Lng,
                        Order = w.Order
                    }).ToList()
                });
            }
        }

        /// <summary>
        /// Delete a route by its ID
        /// </summary>
        [HttpDelete("{id:Guid}")]
        public async Task<IActionResult> DeleteRoute(Guid id)
        {
            var route = await dbContext.ItineraryItemsRoutes
                .Include(r => r.Waypoints)
                .FirstOrDefaultAsync(r => r.Id == id);

            if (route == null)
            {
                return NotFound();
            }

            dbContext.ItineraryItemsRoutes.Remove(route);
            await dbContext.SaveChangesAsync();

            return NoContent();
        }
    }
}
