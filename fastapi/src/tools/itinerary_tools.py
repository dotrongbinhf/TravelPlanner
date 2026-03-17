"""
Itinerary Optimization Tool.

Uses Google OR-Tools VRP (Vehicle Routing Problem) with time windows
to generate optimized daily schedules. Refactored from vrp_time_window.py
into a parameterized, callable function.
"""

import logging
from typing import Any, Optional
from langchain_core.tools import tool
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

logger = logging.getLogger(__name__)


def _minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to HH:MM format."""
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours:02d}:{mins:02d}"


def _solve_vrp(
    time_matrix: list[list[int]],
    time_windows: list[tuple[int, int]],
    service_times: list[int],
    start_index: int,
    end_index: int,
    time_limit_seconds: int = 3,
) -> Optional[list[dict[str, Any]]]:
    """Run the OR-Tools VRP solver with time windows.
    
    Args:
        time_matrix: N×N matrix of travel times in minutes between locations.
        time_windows: List of (earliest, latest) arrival times in minutes since midnight.
        service_times: Duration spent at each location in minutes.
        start_index: Index of the starting location.
        end_index: Index of the ending location.
        time_limit_seconds: Maximum solver time.
        
    Returns:
        Ordered list of scheduled stops, or None if no feasible solution.
    """
    n = len(time_matrix)
    
    manager = pywrapcp.RoutingIndexManager(
        n, 1, [start_index], [end_index]
    )
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return time_matrix[from_node][to_node] + service_times[from_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    routing.AddDimension(
        transit_callback_index,
        1440,   # Max wait time (full day slack)
        1440,   # Max cumulative time (24h horizon)
        False,  # Don't force start to zero
        "Time",
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    # Set time windows
    for idx, tw in enumerate(time_windows):
        if idx == start_index or idx == end_index:
            continue
        index = manager.NodeToIndex(idx)
        time_dimension.CumulVar(index).SetRange(tw[0], tw[1])

    # Start and end time windows
    start_idx = routing.Start(0)
    end_idx = routing.End(0)
    start_tw = time_windows[start_index]
    end_tw = time_windows[end_index]
    time_dimension.CumulVar(start_idx).SetRange(start_tw[0], start_tw[1])
    time_dimension.CumulVar(end_idx).SetRange(end_tw[0], end_tw[1])

    # Search strategy
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = time_limit_seconds

    solution = routing.SolveWithParameters(search_parameters)
    
    if not solution:
        return None

    # Extract route
    route = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        time_var = time_dimension.CumulVar(index)
        node = manager.IndexToNode(index)
        arrival = solution.Min(time_var)
        service = service_times[node]
        departure = arrival + service

        stop = {
            "location_index": node,
            "arrival_time": _minutes_to_time(arrival),
            "arrival_minutes": arrival,
            "service_duration_minutes": service,
            "departure_time": _minutes_to_time(departure),
            "departure_minutes": departure,
        }

        # Check waiting time
        next_index = solution.Value(routing.NextVar(index))
        if not routing.IsEnd(next_index):
            next_node = manager.IndexToNode(next_index)
            travel_time = time_matrix[node][next_node]
            next_arrival = solution.Min(time_dimension.CumulVar(next_index))
            theoretical_arrival = departure + travel_time
            wait_time = next_arrival - theoretical_arrival
            stop["travel_to_next_minutes"] = travel_time
            if wait_time > 0:
                stop["wait_time_minutes"] = wait_time

        route.append(stop)
        index = next_index

    # Add final stop
    time_var = time_dimension.CumulVar(index)
    node = manager.IndexToNode(index)
    route.append({
        "location_index": node,
        "arrival_time": _minutes_to_time(solution.Min(time_var)),
        "arrival_minutes": solution.Min(time_var),
        "service_duration_minutes": 0,
        "departure_time": "",
        "departure_minutes": solution.Min(time_var),
    })

    return route


@tool
async def optimize_daily_itinerary(
    locations: list[dict[str, str]],
    time_matrix: list[list[int]],
    time_windows: list[tuple[int, int]],
    service_times: list[int],
    start_index: int = 0,
    end_index: Optional[int] = None,
) -> dict[str, Any]:
    """Optimize a daily itinerary schedule using VRP with time windows.
    
    Given a list of locations with their travel times and time constraints,
    finds the optimal order to visit them while respecting opening hours
    and minimizing total travel time.
    
    Supports flexible scenarios:
    - Hotel as start AND end (day trip from hotel)
    - Airport as start, hotel as end (arrival day)
    - Hotel as start, airport as end (departure day)
    - Mid-day hotel return for rest
    - Night arrival with morning activities
    
    Args:
        locations: List of dicts with location info. Each must have:
            - "name": Location name
            - "type": Location type (e.g. "hotel", "restaurant", "attraction", "airport")
        time_matrix: N×N matrix of travel times in minutes between all locations.
                     time_matrix[i][j] = minutes to travel from location i to location j.
        time_windows: List of (earliest_minutes, latest_minutes) tuples.
                     Times are in minutes since midnight (e.g. 480 = 08:00, 1200 = 20:00).
                     Use (0, 1440) for flexible locations with no time constraint.
        service_times: List of duration in minutes spent at each location.
                      (e.g. 60 for a 1-hour visit, 90 for lunch, 0 for transit points).
        start_index: Index of starting location in the locations list (default 0).
        end_index: Index of ending location. If None, defaults to last location.

    Returns:
        Optimized schedule with ordered stops, times, and travel info.
    """
    if end_index is None:
        end_index = len(locations) - 1
    
    n = len(locations)
    logger.info(f"[optimize_daily_itinerary] {n} locations, start={start_index}, end={end_index}")
    
    # Validate inputs
    if n < 2:
        return {"error": "Need at least 2 locations (start and end)"}
    if len(time_matrix) != n or any(len(row) != n for row in time_matrix):
        return {"error": f"time_matrix must be {n}×{n}"}
    if len(time_windows) != n:
        return {"error": f"time_windows must have {n} entries"}
    if len(service_times) != n:
        return {"error": f"service_times must have {n} entries"}
    
    # Solve
    route = _solve_vrp(
        time_matrix=time_matrix,
        time_windows=time_windows,
        service_times=service_times,
        start_index=start_index,
        end_index=end_index,
    )
    
    if route is None:
        logger.warning("[optimize_daily_itinerary] No feasible solution found")
        return {
            "success": False,
            "error": "No feasible schedule found. Try relaxing time windows or removing locations.",
            "locations": locations,
        }
    
    # Enrich route with location info
    schedule = []
    total_travel = 0
    total_wait = 0
    
    for stop in route:
        idx = stop["location_index"]
        loc = locations[idx]
        entry = {
            "name": loc.get("name", f"Location {idx}"),
            "type": loc.get("type", "unknown"),
            "arrival_time": stop["arrival_time"],
            "duration_minutes": stop["service_duration_minutes"],
            "departure_time": stop["departure_time"],
        }
        
        if "travel_to_next_minutes" in stop:
            entry["travel_to_next_minutes"] = stop["travel_to_next_minutes"]
            total_travel += stop["travel_to_next_minutes"]
        if "wait_time_minutes" in stop:
            entry["wait_time_minutes"] = stop["wait_time_minutes"]
            total_wait += stop["wait_time_minutes"]
            
        # Preserve any extra location fields (e.g. place_id, lat, lng)
        for key in loc:
            if key not in entry:
                entry[key] = loc[key]
        
        schedule.append(entry)
    
    first_departure = route[0]["departure_minutes"]
    last_arrival = route[-1]["arrival_minutes"]
    
    result = {
        "success": True,
        "schedule": schedule,
        "summary": {
            "total_locations": len(schedule),
            "first_departure": _minutes_to_time(first_departure),
            "last_arrival": _minutes_to_time(last_arrival),
            "total_active_minutes": last_arrival - first_departure,
            "total_travel_minutes": total_travel,
            "total_wait_minutes": total_wait,
        }
    }
    
    logger.info(f"[optimize_daily_itinerary] Success: {len(schedule)} stops, "
                f"{total_travel}min travel, {total_wait}min wait")
    return result
