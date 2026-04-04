"""
Itinerary VRP Solver Tool.

Multi-day VRP (Vehicle Routing Problem) with time windows using Google OR-Tools.
Each day = 1 vehicle. Accepts structured location input and produces an optimized
multi-day itinerary.

Moved from standalone vrp_time_window.py into a proper tool for LLM agents.
"""

import json
import math
import logging
from typing import Any, Optional
from langchain_core.tools import tool
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

from src.tools.maps_tools import compute_route_matrix, LOCAL_TRANSPORT_MAP

logger = logging.getLogger(__name__)


# ============================================================================
# UTILITIES
# ============================================================================

def minutes_to_time(minutes: int) -> str:
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours:02d}:{mins:02d}"


# ============================================================================
# NODE BUILDING
# ============================================================================

def _determine_num_days(locations: list[dict]) -> int:
    """Number of days = Number of hotels + 1."""
    hotel_count = sum(1 for loc in locations if loc["type"] == "hotel")
    return hotel_count + 1


def _build_nodes(locations: list[dict], num_days: int) -> dict:
    """
    Từ danh sách locations đầu vào, sinh ra tất cả VRP nodes.
    
    Returns:
        data dict chứa: nodes, time_windows, service_times, starts, ends,
                         lunch_nodes, dinner_nodes, vehicle_lunch_cap, vehicle_dinner_cap,
                         mandatory_node_indices, closed_day_constraints,
                         drop_luggage_info, pickup_luggage_info, break_nodes,
                         disjunction_groups
    """
    nodes = []
    time_windows = []
    service_times = []
    starts = []
    ends = []
    
    disjunction_groups = {}
    lunch_nodes = []
    dinner_nodes = []
    mandatory_node_indices = set()
    closed_day_constraints = []
    drop_luggage_info = None
    pickup_luggage_info = None
    break_nodes = []
    
    # --- Extract key locations ---
    outbound = next((l for l in locations if l["type"] == "outbound"), None)
    return_loc = next((l for l in locations if l["type"] == "return"), None)
    hotels = sorted(
        [l for l in locations if l["type"] == "hotel"],
        key=lambda h: h["day"]
    )
    attractions = [l for l in locations if l["type"] == "attraction"]
    restaurants = [l for l in locations if l["type"] == "restaurant"]
    
    if not outbound or not return_loc:
        raise ValueError("At least 1 'outbound' and 1 'return' location are required.")
    if len(hotels) != num_days - 1:
        raise ValueError(f"Need {num_days - 1} hotels for {num_days} days, but got {len(hotels)}.")

    def _add_node(name, lat, lng, tw, svc, role):
        idx = len(nodes)
        nodes.append({"name": name, "lat": lat, "lng": lng, "role": role})
        time_windows.append(tw)
        service_times.append(svc)
        return idx

    # ---- STEP 1: Build Start/End nodes for each day (0-based) ----
    for day in range(num_days):
        if day == 0:
            start_idx = _add_node(
                f"{outbound['name']} (Start)",
                outbound["location"]["lat"], outbound["location"]["lng"],
                outbound.get("time_window", (480, 720)), 30, "start"
            )
        else:
            prev_hotel = hotels[day - 1]
            curr_hotel_tonight = hotels[day] if day < len(hotels) else None
            is_checkout = (
                day == num_days - 1
                or curr_hotel_tonight is None
                or prev_hotel["name"] != curr_hotel_tonight["name"]
            )
            if is_checkout:
                start_idx = _add_node(
                    f"{prev_hotel['name']} (Checkout)",
                    prev_hotel["location"]["lat"], prev_hotel["location"]["lng"],
                    prev_hotel.get("checkout_time", (480, 540)), 0, "start"
                )
            else:
                start_idx = _add_node(
                    f"{prev_hotel['name']} (Leave hotel)",
                    prev_hotel["location"]["lat"], prev_hotel["location"]["lng"],
                    (420, 540), 0, "start"
                )
        starts.append(start_idx)
        
        if day == num_days - 1:
            end_idx = _add_node(
                f"{return_loc['name']} (End)",
                return_loc["location"]["lat"], return_loc["location"]["lng"],
                return_loc.get("time_window", (900, 1440)), 0, "end"
            )
        else:
            hotel = hotels[day]
            prev_hotel_last_night = hotels[day - 1] if day > 0 else None
            is_checkin = (
                day == 0
                or prev_hotel_last_night is None
                or hotel["name"] != prev_hotel_last_night["name"]
            )
            if is_checkin:
                end_idx = _add_node(
                    f"{hotel['name']} (Check-in)",
                    hotel["location"]["lat"], hotel["location"]["lng"],
                    hotel.get("checkin_time", (1020, 1440)), 0, "end"
                )
            else:
                end_idx = _add_node(
                    f"{hotel['name']} (Return to hotel)",
                    hotel["location"]["lat"], hotel["location"]["lng"],
                    (1020, 1440), 0, "end"
                )
        ends.append(end_idx)

    # ---- STEP 2: Add attraction nodes ----
    for attr in attractions:
        tw = attr.get("time_window", (480, 1080))
        duration = attr.get("duration", 60)
        adjusted_tw = (tw[0], max(tw[0], tw[1] - duration))
        
        idx = _add_node(
            attr["name"],
            attr["location"]["lat"], attr["location"]["lng"],
            adjusted_tw,
            duration,
            "attraction"
        )
        if attr.get("must_visit", False):
            mandatory_node_indices.add(idx)
        
        closed_days = attr.get("closed_days", [])
        if closed_days:
            allowed_vehicles = [v for v in range(num_days) if v not in closed_days]
            closed_day_constraints.append((idx, allowed_vehicles))
        
        group_id = attr.get("_disjunction_group")
        if group_id:
            disjunction_groups.setdefault(group_id, []).append(idx)

    # ---- STEP 3: Add restaurant nodes ----
    for rest in restaurants:
        idx = _add_node(
            rest["name"],
            rest["location"]["lat"], rest["location"]["lng"],
            rest.get("time_window", (660, 810)),
            rest.get("duration", 60),
            "restaurant"
        )
        meal = rest.get("meal", "lunch")
        if meal == "lunch":
            lunch_nodes.append(idx)
        else:
            dinner_nodes.append(idx)
        mandatory_node_indices.add(idx)

    # ---- STEP 4: Add auxiliary nodes (luggage, breaks) ----
    if outbound.get("drop_luggage", False) and len(hotels) > 0:
        first_hotel = hotels[0]
        idx = _add_node(
            f"{first_hotel['name']} (Drop luggage)",
            first_hotel["location"]["lat"], first_hotel["location"]["lng"],
            (480, 720), 30, "drop_luggage"
        )
        drop_luggage_info = (idx, 0)
        mandatory_node_indices.add(idx)

    if return_loc.get("pickup_luggage", False) and len(hotels) > 0:
        last_hotel = hotels[-1]
        idx = _add_node(
            f"{last_hotel['name']} (Pick up luggage)",
            last_hotel["location"]["lat"], last_hotel["location"]["lng"],
            (600, 1440), 30, "pickup_luggage"
        )
        pickup_luggage_info = (idx, num_days - 1)
        mandatory_node_indices.add(idx)

    for hotel in hotels:
        if hotel.get("break_time_window"):
            break_day_vehicle = hotel["day"]
            if break_day_vehicle < num_days:
                idx = _add_node(
                    f"{hotel['name']} (Midday rest)",
                    hotel["location"]["lat"], hotel["location"]["lng"],
                    hotel["break_time_window"],
                    hotel.get("break_duration", 120),
                    "break"
                )
                break_nodes.append((idx, break_day_vehicle))
                mandatory_node_indices.add(idx)

    # ---- STEP 5: Compute meal break info (for break intervals in solver) ----
    num_lunch_needed = num_days
    num_dinner_needed = num_days
    
    return_tw = return_loc.get("time_window", (900, 1440))
    # Skip dinner on last day if return departure is too early (any transport mode)
    if return_tw[1] <= 1080:  # departure before 18:00
        num_dinner_needed = num_days - 1

    # Collect allowed_days constraints from attractions
    allowed_days_constraints = []
    for attr in attractions:
        allowed_days = attr.get("allowed_days")
        if allowed_days is not None:
            # Find the node index for this attraction
            attr_name = attr["name"]
            for idx, node in enumerate(nodes):
                if node["name"] == attr_name and node["role"] == "attraction":
                    allowed_days_constraints.append((idx, allowed_days))

    return {
        "nodes": nodes,
        "time_windows": time_windows,
        "service_times": service_times,
        "num_vehicles": num_days,
        "starts": starts,
        "ends": ends,
        "num_lunch_needed": num_lunch_needed,
        "num_dinner_needed": num_dinner_needed,
        "mandatory_node_indices": mandatory_node_indices,
        "closed_day_constraints": closed_day_constraints,
        "allowed_days_constraints": allowed_days_constraints,
        "drop_luggage_info": drop_luggage_info,
        "pickup_luggage_info": pickup_luggage_info,
        "break_nodes": break_nodes,
        "disjunction_groups": disjunction_groups,
    }


# ============================================================================
# DISTANCE MATRIX (uses maps_tools.compute_route_matrix)
# ============================================================================

def _deduplicate_locations(nodes: list[dict]) -> tuple[list[tuple], dict, list]:
    """Deduplicate coordinates. Nodes with lat=0,lng=0 are generic (flat distance)."""
    unique_locs = []
    coord_to_idx = {}
    node_to_unique = {}
    generic_nodes = []
    
    for i, node in enumerate(nodes):
        if node["lat"] == 0 and node["lng"] == 0:
            generic_nodes.append(i)
            continue
        coord_key = (round(node["lat"], 6), round(node["lng"], 6))
        if coord_key not in coord_to_idx:
            coord_to_idx[coord_key] = len(unique_locs)
            unique_locs.append(coord_key)
        node_to_unique[i] = coord_to_idx[coord_key]
    
    return unique_locs, node_to_unique, generic_nodes


def _euclidean_matrix(locations: list[tuple]) -> list[list[int]]:
    """Fallback: Euclidean distance mock (30 km/h average)."""
    n = len(locations)
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                dist = math.hypot(
                    (locations[i][0] - locations[j][0]) * 111,
                    (locations[i][1] - locations[j][1]) * 111
                    * math.cos(math.radians(locations[i][0])),
                )
                matrix[i][j] = max(5, int(dist / 30 * 60))
    return matrix


async def _build_distance_matrix(
    nodes: list[dict],
    use_api: bool = False,
    travel_mode: str = "DRIVE",
    generic_distance: int = 15,
) -> list[list[int]]:
    """
    Build full NxN time matrix.
    - Deduplicates coordinates to minimize API calls.
    - Generic nodes (lat=0, lng=0) get flat distance to all others.
    - Uses Routes API with travelMode when use_api=True.
    """
    n = len(nodes)
    unique_locs, node_to_unique, generic_nodes = _deduplicate_locations(nodes)
    
    # Fetch matrix for unique real locations
    if use_api and len(unique_locs) > 0:
        unique_matrix = await compute_route_matrix(
            unique_locs, travel_mode=travel_mode
        )
    else:
        unique_matrix = _euclidean_matrix(unique_locs)
    
    # Expand into full NxN matrix
    matrix = [[0] * n for _ in range(n)]
    
    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 0
            elif i in generic_nodes or j in generic_nodes:
                matrix[i][j] = generic_distance
            else:
                ui = node_to_unique[i]
                uj = node_to_unique[j]
                matrix[i][j] = unique_matrix[ui][uj]
    
    return matrix


# ============================================================================
# SOLVER
# ============================================================================

@tool
async def solve_vrp(
    locations: list[dict],
    use_api: bool = False,
    travel_mode: str = "DRIVE",
    generic_distance: int = 15,
    time_limit_seconds: int = 3,
) -> dict:
    """
    Core VRP solver function.
    
    Args:
        locations: List of location dicts with type, name, location, etc.
        use_api: Whether to call Google Maps Routes API (False = Euclidean mock).
        travel_mode: Routes API travelMode (DRIVE, TWO_WHEELER, WALK, TRANSIT).
        generic_distance: Default travel time (minutes) for auto-generated restaurants.
        time_limit_seconds: Solver time limit.
    
    Returns:
        {
            "days": [{"day": int, "stops": [...]}],
            "dropped": [str],
            "objective": int,
            "objective_breakdown": {...},
        }
    """
    logger.info(f"[solve_vrp] {len(locations)} locations, travel_mode={travel_mode}")

    # ---- Step 1: Determine days & build nodes ----
    num_days = _determine_num_days(locations)
    data = _build_nodes(locations, num_days)
    
    # ---- Step 2: Build distance matrix + apply travel buffer ----
    raw_matrix = await _build_distance_matrix(
        data["nodes"], use_api=use_api, travel_mode=travel_mode,
        generic_distance=generic_distance
    )
    # Buffer: round up to 15 min + 15 min extra (rest + traffic safety)
    n_nodes = len(data["nodes"])
    buffered_matrix = [[0] * n_nodes for _ in range(n_nodes)]
    for i in range(n_nodes):
        for j in range(n_nodes):
            t = raw_matrix[i][j]
            if t > 0:
                buffered_matrix[i][j] = math.ceil(t / 15) * 15 + 15
            else:
                buffered_matrix[i][j] = 0
    data["time_matrix"] = buffered_matrix
    data["raw_time_matrix"] = raw_matrix
    
    # ---- Step 3: Create routing model ----
    n = len(data["nodes"])
    manager = pywrapcp.RoutingIndexManager(
        n, data["num_vehicles"], data["starts"], data["ends"]
    )
    routing = pywrapcp.RoutingModel(manager)
    
    # ---- Time callback ----
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data["time_matrix"][from_node][to_node] + data["service_times"][from_node]
    
    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    # ---- Time dimension ----
    routing.AddDimension(
        transit_callback_index,
        1440, 1440, False, "Time"
    )
    time_dimension = routing.GetDimensionOrDie("Time")

    # minimizes the length of the longest route.
    time_dimension.SetGlobalSpanCostCoefficient(10)
    # Minimize total operating time across all vehicles
    time_dimension.SetSpanCostCoefficientForAllVehicles(10)
    
    # ---- Solver (needed for break intervals and constraints) ----
    solver = routing.solver()

    # ---- Meal break intervals (replace generic meal nodes) ----
    # Build node_visit_transits for SetBreakIntervalsOfVehicle
    node_visit_transits = [0] * (routing.Size() + routing.vehicles())
    for i in range(n):
        idx = manager.NodeToIndex(i)
        if idx >= 0:
            node_visit_transits[idx] = data["service_times"][i]
    
    num_lunch = data["num_lunch_needed"]
    num_dinner = data["num_dinner_needed"]
    
    # Store break interval vars for solution extraction
    vehicle_breaks: dict[int, list[tuple[str, any]]] = {}  # {vehicle_id: [(meal_name, IntervalVar)]}
    
    for v in range(data["num_vehicles"]):
        breaks = []
        vehicle_breaks[v] = []
        
        # Get vehicle time window bounds to check feasibility
        v_start_tw = data["time_windows"][data["starts"][v]]
        v_end_tw = data["time_windows"][data["ends"][v]]
        v_earliest_start = v_start_tw[0]  # Earliest departure
        v_latest_end = v_end_tw[1]        # Latest arrival at end
        
        # Lunch break: 90min, must start between 11:00-13:00
        # Feasible if: vehicle starts before 13:00 AND vehicle ends after 11:00 + 90 = 12:30
        lunch_start_min, lunch_start_max, lunch_duration = 660, 780, 90
        if (v < num_lunch 
            and v_earliest_start <= lunch_start_max
            and v_latest_end >= lunch_start_min + lunch_duration):
            lunch_break = solver.FixedDurationIntervalVar(
                lunch_start_min, lunch_start_max, lunch_duration, False, f"lunch_day_{v}"
            )
            breaks.append(lunch_break)
            vehicle_breaks[v].append(("Lunch", lunch_break))
            logger.info(f"[solve_vrp] Day {v}: Lunch break added (window {v_earliest_start}-{v_latest_end})")
        else:
            logger.info(f"[solve_vrp] Day {v}: Lunch SKIPPED (window {v_earliest_start}-{v_latest_end})")
        
        # Dinner break: 90min, must start between 18:00-21:00
        # Feasible if: vehicle ends after 18:00 + 90 = 19:30
        dinner_start_min, dinner_start_max, dinner_duration = 1080, 1260, 90
        if (v < num_dinner
            and v_latest_end >= dinner_start_min + dinner_duration):
            dinner_break = solver.FixedDurationIntervalVar(
                dinner_start_min, dinner_start_max, dinner_duration, False, f"dinner_day_{v}"
            )
            breaks.append(dinner_break)
            vehicle_breaks[v].append(("Dinner", dinner_break))
            logger.info(f"[solve_vrp] Day {v}: Dinner break added (window {v_earliest_start}-{v_latest_end})")
        else:
            logger.info(f"[solve_vrp] Day {v}: Dinner SKIPPED (window {v_earliest_start}-{v_latest_end})")
        
        if breaks:
            time_dimension.SetBreakIntervalsOfVehicle(
                breaks, v, node_visit_transits
            )
    
    # ---- Time windows ----
    for loc_idx, tw in enumerate(data["time_windows"]):
        if loc_idx in data["starts"] or loc_idx in data["ends"]:
            continue
        index = manager.NodeToIndex(loc_idx)
        time_dimension.CumulVar(index).SetRange(tw[0], tw[1])
    
    for i in range(data["num_vehicles"]):
        s_idx = routing.Start(i)
        e_idx = routing.End(i)
        s_tw = data["time_windows"][data["starts"][i]]
        e_tw = data["time_windows"][data["ends"][i]]
        time_dimension.CumulVar(s_idx).SetRange(s_tw[0], s_tw[1])
        time_dimension.CumulVar(e_idx).SetRange(e_tw[0], e_tw[1])
    
    # ---- Solver-level constraints ----
    
    if data["drop_luggage_info"]:
        node_idx, vehicle_idx = data["drop_luggage_info"]
        routing_idx = manager.NodeToIndex(node_idx)
        routing.SetAllowedVehiclesForIndex([vehicle_idx], routing_idx)
        solver.Add(routing.NextVar(routing.Start(vehicle_idx)) == routing_idx)
    
    if data["pickup_luggage_info"]:
        node_idx, vehicle_idx = data["pickup_luggage_info"]
        routing_idx = manager.NodeToIndex(node_idx)
        routing.SetAllowedVehiclesForIndex([vehicle_idx], routing_idx)
        solver.Add(routing.NextVar(routing_idx) == routing.End(vehicle_idx))
    
    for node_idx, vehicle_idx in data["break_nodes"]:
        routing_idx = manager.NodeToIndex(node_idx)
        routing.SetAllowedVehiclesForIndex([vehicle_idx], routing_idx)
    
    for node_idx, allowed_vehicles in data["closed_day_constraints"]:
        routing_idx = manager.NodeToIndex(node_idx)
        routing.SetAllowedVehiclesForIndex(allowed_vehicles, routing_idx)
    
    # ---- Allowed days constraints (from attraction segments) ----
    for node_idx, allowed_days in data["allowed_days_constraints"]:
        routing_idx = manager.NodeToIndex(node_idx)
        routing.SetAllowedVehiclesForIndex(allowed_days, routing_idx)
    
    # ---- Disjunction ----
    penalty = 10000
    non_droppable = set(data["starts"]) | set(data["ends"]) | data["mandatory_node_indices"]
    handled_by_group = set()
    
    for group_id, group_node_indices in data.get("disjunction_groups", {}).items():
        routing_indices = [int(manager.NodeToIndex(n)) for n in group_node_indices]
        any_mandatory = any(n in data["mandatory_node_indices"] for n in group_node_indices)
        if any_mandatory:
            routing.AddDisjunction(routing_indices, 100000)
        else:
            routing.AddDisjunction(routing_indices, penalty)
        handled_by_group.update(group_node_indices)
    
    for node in range(n):
        if node in non_droppable or node in handled_by_group:
            continue
        index = int(manager.NodeToIndex(node))
        routing.AddDisjunction([index], penalty)
    
    # ---- Search parameters ----
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = time_limit_seconds
    
    # ---- Solve ----
    solution = routing.SolveWithParameters(search_parameters)
    
    if not solution:
        return {
            "error": True,
            "status": routing.status(),
            "message": "No solution found. Check time windows or reduce the number of locations.",
            "days": [],
            "dropped": [],
            "objective": -1,
        }
    
    # ---- Extract solution ----
    result_days = []
    for vehicle_id in range(data["num_vehicles"]):
        # Get scheduled meal breaks for this vehicle from the solution
        scheduled_breaks = []
        for meal_name, break_var in vehicle_breaks.get(vehicle_id, []):
            break_start = solution.Value(break_var.StartExpr())
            break_end = break_start + 90
            scheduled_breaks.append({
                "name": meal_name,
                "role": "meal_break",
                "arrival": minutes_to_time(break_start),
                "arrival_minutes": break_start,
                "departure": minutes_to_time(break_end),
                "departure_minutes": break_end,
                "duration": 90,
                "travel_to_next": 0,
                "buffer": 0,
                "travel_to_next_buffered": 0,
                "wait": 0,
            })
        # Sort breaks by start time
        scheduled_breaks.sort(key=lambda b: b["arrival_minutes"])
        
        # Build stop list, inserting breaks at correct positions
        day_stops = []
        index = routing.Start(vehicle_id)
        break_cursor = 0  # Track which breaks have been inserted
        
        while not routing.IsEnd(index):
            time_var = time_dimension.CumulVar(index)
            node_idx = manager.IndexToNode(index)
            arrival = solution.Min(time_var)
            svc = data["service_times"][node_idx]
            departure = arrival + svc
            
            stop = {
                "name": data["nodes"][node_idx]["name"],
                "role": data["nodes"][node_idx]["role"],
                "arrival": minutes_to_time(arrival),
                "arrival_minutes": arrival,
                "departure": minutes_to_time(departure),
                "departure_minutes": departure,
                "duration": svc,
                "travel_to_next": 0,
                "buffer": 0,
                "travel_to_next_buffered": 0,
                "wait": 0,
            }
            
            next_index = solution.Value(routing.NextVar(index))
            next_node = manager.IndexToNode(next_index)
            raw_travel = data["raw_time_matrix"][node_idx][next_node]
            buffered_travel = data["time_matrix"][node_idx][next_node]
            stop["travel_to_next"] = raw_travel
            stop["buffer"] = buffered_travel - raw_travel
            stop["travel_to_next_buffered"] = buffered_travel

            if not routing.IsEnd(next_index):
                next_arrival = solution.Min(time_dimension.CumulVar(next_index))
                expected_next = departure + buffered_travel
                stop["wait"] = max(0, next_arrival - expected_next)
            
            day_stops.append(stop)
            
            # Insert any meal breaks that occur between this stop's departure
            # and the next stop's arrival
            while break_cursor < len(scheduled_breaks):
                brk = scheduled_breaks[break_cursor]
                if brk["arrival_minutes"] >= departure:
                    if routing.IsEnd(next_index) or brk["arrival_minutes"] < solution.Min(time_dimension.CumulVar(next_index)):
                        day_stops.append(brk)
                        break_cursor += 1
                    else:
                        break
                else:
                    break_cursor += 1  # Break before this stop, skip
            
            index = next_index
        
        # Add final stop (End node)
        time_var = time_dimension.CumulVar(index)
        node_idx = manager.IndexToNode(index)
        arrival = solution.Min(time_var)
        day_stops.append({
            "name": data["nodes"][node_idx]["name"],
            "role": data["nodes"][node_idx]["role"],
            "arrival": minutes_to_time(arrival),
            "arrival_minutes": arrival,
            "departure": "",
            "departure_minutes": 0,
            "duration": 0,
            "travel_to_next": 0,
            "buffer": 0,
            "travel_to_next_buffered": 0,
            "wait": 0,
        })
        
        # Insert any remaining breaks before end
        while break_cursor < len(scheduled_breaks):
            brk = scheduled_breaks[break_cursor]
            # Insert before the last stop (end node)
            day_stops.insert(-1, brk)
            break_cursor += 1
        
        result_days.append({"day": vehicle_id, "stops": day_stops})
    
    # Find dropped nodes
    dropped = []
    for node in range(routing.Size()):
        if routing.IsStart(node) or routing.IsEnd(node):
            continue
        if solution.Value(routing.NextVar(node)) == node:
            real_node = manager.IndexToNode(node)
            dropped.append(data["nodes"][real_node]["name"])
    
    # ---- Objective breakdown ----
    total_arc_cost = 0
    total_slack = 0
    all_start_cumuls = []
    all_end_cumuls = []
    vehicle_spans = []
    
    for vehicle_id in range(data["num_vehicles"]):
        index = routing.Start(vehicle_id)
        start_cumul = solution.Min(time_dimension.CumulVar(index))
        all_start_cumuls.append(start_cumul)
        
        while not routing.IsEnd(index):
            node_idx = manager.IndexToNode(index)
            next_index = solution.Value(routing.NextVar(index))
            next_node = manager.IndexToNode(next_index)
            transit = data["time_matrix"][node_idx][next_node] + data["service_times"][node_idx]
            total_arc_cost += transit
            
            cumul_current = solution.Min(time_dimension.CumulVar(index))
            cumul_next = solution.Min(time_dimension.CumulVar(next_index))
            slack = cumul_next - cumul_current - transit
            if slack > 0:
                total_slack += slack
            
            index = next_index
        
        end_cumul = solution.Min(time_dimension.CumulVar(index))
        all_end_cumuls.append(end_cumul)
        vehicle_spans.append(end_cumul - start_cumul)
    
    global_span = max(all_end_cumuls) - min(all_start_cumuls) if all_end_cumuls else 0
    
    dropped_penalties = 0
    for node in range(routing.Size()):
        if routing.IsStart(node) or routing.IsEnd(node):
            continue
        if solution.Value(routing.NextVar(node)) == node:
            real_node = manager.IndexToNode(node)
            is_in_group = False
            for group_id, group_nodes in data.get("disjunction_groups", {}).items():
                if real_node in group_nodes:
                    any_mandatory = any(n in data["mandatory_node_indices"] for n in group_nodes)
                    dropped_penalties += 100000 if any_mandatory else penalty
                    is_in_group = True
                    break
            if not is_in_group:
                dropped_penalties += penalty
    
    slack_cost = total_slack * 50
    global_span_cost = global_span * 100
    sum_components = total_arc_cost + slack_cost + global_span_cost + dropped_penalties
    
    objective_breakdown = {
        "total_objective": solution.ObjectiveValue(),
        "sum_components": sum_components,
        "arc_cost": total_arc_cost,
        "total_slack": total_slack,
        "slack_cost": slack_cost,
        "global_span": global_span,
        "global_span_cost": global_span_cost,
        "dropped_count": len(dropped),
        "dropped_penalty": dropped_penalties,
        "vehicle_spans": vehicle_spans,
        "vehicle_start_cumuls": all_start_cumuls,
        "vehicle_end_cumuls": all_end_cumuls,
    }
    
    return {
        "error": False,
        "days": result_days,
        "dropped": dropped,
        "objective": solution.ObjectiveValue(),
        "objective_breakdown": objective_breakdown,
    }

