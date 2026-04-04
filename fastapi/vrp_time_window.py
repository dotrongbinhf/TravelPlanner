#!/usr/bin/env python3
# Only use for test - Legacy
"""
Generalized VRP with Time Windows Solver.

Accepts structured location input (outbound, return, hotel, attraction, restaurant)
and produces an optimized multi-day itinerary using Google OR-Tools.

Usage:
    result = solve_vrp(locations)
    # result = {"days": [...], "dropped": [...], "objective": int}
"""
import math
import logging
from typing import Optional
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from src.config import settings

logger = logging.getLogger(__name__)

# MOCKs
ROUTE_MATRIX_MOCK = [{'originIndex': 9, 'destinationIndex': 9, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 7, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 1, 'status': {}, 'duration': '598s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 3, 'status': {}, 'duration': '606s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 7, 'status': {}, 'duration': '755s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 2, 'status': {}, 'duration': '765s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 6, 'status': {}, 'duration': '785s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 8, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 0, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 3, 'status': {}, 'duration': '519s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 8, 'status': {}, 'duration': '370s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 4, 'status': {}, 'duration': '419s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 9, 'status': {}, 'duration': '463s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 2, 'status': {}, 'duration': '717s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 3, 'status': {}, 'duration': '468s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 1, 'status': {}, 'duration': '647s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 6, 'status': {}, 'duration': '737s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 1, 'status': {}, 'duration': '197s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 2, 'status': {}, 'duration': '202s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 8, 'status': {}, 'duration': '618s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 7, 'status': {}, 'duration': '706s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 1, 'status': {}, 'duration': '316s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 0, 'status': {}, 'duration': '2159s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 5, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 9, 'status': {}, 'duration': '674s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 8, 'status': {}, 'duration': '312s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 5, 'status': {}, 'duration': '1367s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 6, 'status': {}, 'duration': '222s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 5, 'status': {}, 'duration': '1101s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 4, 'status': {}, 'duration': '732s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 8, 'status': {}, 'duration': '678s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 4, 'status': {}, 'duration': '399s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 9, 'status': {}, 'duration': '713s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 9, 'destinationIndex': 5, 'status': {}, 'duration': '1021s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 6, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 3, 'status': {}, 'duration': '595s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 6, 'status': {}, 'duration': '875s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 7, 'status': {}, 'duration': '813s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 2, 'status': {}, 'duration': '123s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 3, 'status': {}, 'duration': '541s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 3, 'status': {}, 'duration': '981s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 2, 'status': {}, 'duration': '2714s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 7, 'status': {}, 'duration': '605s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 5, 'status': {}, 'duration': '1039s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 9, 'status': {}, 'duration': '1119s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 7, 'status': {}, 'duration': '845s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 7, 'status': {}, 'duration': '119s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 2, 'status': {}, 'duration': '855s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 2, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 8, 'status': {}, 'duration': '600s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 9, 'status': {}, 'duration': '895s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 1, 'status': {}, 'duration': '562s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 4, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 1, 'status': {}, 'duration': '2596s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 1, 'status': {}, 'duration': '437s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 4, 'status': {}, 'duration': '792s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 6, 'status': {}, 'duration': '1528s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 2, 'status': {}, 'duration': '823s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 3, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 8, 'status': {}, 'duration': '484s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 3, 'status': {}, 'duration': '297s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 5, 'status': {}, 'duration': '1351s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 0, 'status': {}, 'duration': '1907s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 6, 'status': {}, 'duration': '636s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 9, 'status': {}, 'duration': '680s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 2, 'status': {}, 'duration': '304s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 6, 'status': {}, 'duration': '843s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 6, 'status': {}, 'duration': '324s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 0, 'status': {}, 'duration': '2393s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 4, 'status': {}, 'duration': '714s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 3, 'status': {}, 'duration': '458s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 5, 'status': {}, 'duration': '899s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 1, 'status': {}, 'duration': '0s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 9, 'status': {}, 'duration': '516s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 2, 'status': {}, 'duration': '1507s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 9, 'status': {}, 'duration': '715s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 5, 'status': {}, 'duration': '1932s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 7, 'status': {}, 'duration': '1497s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 8, 'status': {}, 'duration': '1113s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 1, 'status': {}, 'duration': '526s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 9, 'status': {}, 'duration': '2103s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 6, 'status': {}, 'duration': '2734s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 8, 'destinationIndex': 0, 'status': {}, 'duration': '2245s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 8, 'status': {}, 'duration': '434s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 5, 'status': {}, 'duration': '1233s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 0, 'status': {}, 'duration': '2462s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 2, 'destinationIndex': 0, 'status': {}, 'duration': '2665s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 1, 'status': {}, 'duration': '1294s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 4, 'destinationIndex': 0, 'status': {}, 'duration': '2298s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 4, 'status': {}, 'duration': '598s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 8, 'status': {}, 'duration': '2473s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 0, 'status': {}, 'duration': '2396s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 4, 'status': {}, 'duration': '2378s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 3, 'status': {}, 'duration': '2533s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 0, 'destinationIndex': 7, 'status': {}, 'duration': '2703s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 6, 'destinationIndex': 5, 'status': {}, 'duration': '1428s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 3, 'destinationIndex': 4, 'status': {}, 'duration': '437s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 1, 'destinationIndex': 7, 'status': {}, 'duration': '293s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 7, 'destinationIndex': 0, 'status': {}, 'duration': '2355s', 'condition': 'ROUTE_EXISTS'}, {'originIndex': 5, 'destinationIndex': 4, 'status': {}, 'duration': '953s', 'condition': 'ROUTE_EXISTS'}]

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
    """Số ngày = Số hotel + 1."""
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
                         loc_coords (for distance matrix)
    """
    nodes = []        # List of {"name": str, "lat": float, "lng": float, "role": str}
    time_windows = []
    service_times = []
    starts = []
    ends = []
    
    # Track metadata
    disjunction_groups = {}  # group_id -> list of node indices
    lunch_nodes = []
    dinner_nodes = []
    mandatory_node_indices = set()
    closed_day_constraints = []  # (node_index, allowed_vehicle_indices)
    drop_luggage_info = None     # (node_index, vehicle_index)
    pickup_luggage_info = None   # (node_index, vehicle_index)
    break_nodes = []             # (node_index, vehicle_index)
    
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
        raise ValueError("Cần có ít nhất 1 'outbound' và 1 'return' trong locations.")
    if len(hotels) != num_days - 1:
        raise ValueError(f"Cần có {num_days - 1} hotel cho {num_days} ngày, nhưng chỉ có {len(hotels)}.")

    def _add_node(name, lat, lng, tw, svc, role):
        idx = len(nodes)
        nodes.append({"name": name, "lat": lat, "lng": lng, "role": role})
        time_windows.append(tw)
        service_times.append(svc)
        return idx

    # ---- STEP 1: Build Start/End nodes for each day (0-based) ----
    for day in range(num_days):
        if day == 0:
            # Day 0 Start = Outbound (service_time=30 for airport processing)
            start_idx = _add_node(
                f"{outbound['name']} (Xuất phát)",
                outbound["location"]["lat"], outbound["location"]["lng"],
                outbound.get("time_window", (480, 720)), 30, "start"
            )
        else:
            prev_hotel = hotels[day - 1]
            # Check if this is a real checkout or just leaving the hotel
            # Real checkout = either last day or switching to a different hotel
            curr_hotel_tonight = hotels[day] if day < len(hotels) else None
            is_checkout = (
                day == num_days - 1  # Last day = always checkout
                or curr_hotel_tonight is None
                or prev_hotel["name"] != curr_hotel_tonight["name"]
            )
            if is_checkout:
                start_idx = _add_node(
                    f"{prev_hotel['name']} (Trả phòng)",
                    prev_hotel["location"]["lat"], prev_hotel["location"]["lng"],
                    prev_hotel.get("checkout_time", (480, 540)), 0, "start"
                )
            else:
                # Same hotel tonight → just leaving for the day (more flexible time)
                start_idx = _add_node(
                    f"{prev_hotel['name']} (Rời khách sạn)",
                    prev_hotel["location"]["lat"], prev_hotel["location"]["lng"],
                    (420, 540), 0, "start"  # 07:00 - 09:00
                )
        starts.append(start_idx)
        
        if day == num_days - 1:
            # Last Day End = Return
            end_idx = _add_node(
                f"{return_loc['name']} (Kết thúc)",
                return_loc["location"]["lat"], return_loc["location"]["lng"],
                return_loc.get("time_window", (900, 1440)), 0, "end"
            )
        else:
            hotel = hotels[day]
            # Check if this is first night at this hotel (check-in) or just returning
            prev_hotel_last_night = hotels[day - 1] if day > 0 else None
            is_checkin = (
                day == 0  # First night = always check-in
                or prev_hotel_last_night is None
                or hotel["name"] != prev_hotel_last_night["name"]
            )
            if is_checkin:
                end_idx = _add_node(
                    f"{hotel['name']} (Nhận phòng)",
                    hotel["location"]["lat"], hotel["location"]["lng"],
                    hotel.get("checkin_time", (1020, 1440)), 0, "end"
                )
            else:
                # Same hotel as last night → just returning (more flexible time)
                end_idx = _add_node(
                    f"{hotel['name']} (Về khách sạn)",
                    hotel["location"]["lat"], hotel["location"]["lng"],
                    (1020, 1440), 0, "end"  # 17:00 - 24:00
                )
        ends.append(end_idx)

    # ---- STEP 2: Add attraction nodes ----
    for attr in attractions:
        tw = attr.get("time_window", (480, 1080))
        duration = attr.get("duration", 60)
        # Adjust time_window end: must arrive early enough to finish before closing
        # arrival + duration <= closing_time → arrival <= closing_time - duration
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
        
        # Closed days → Only allow specific vehicles (all 0-based)
        closed_days = attr.get("closed_days", [])
        if closed_days:
            allowed_vehicles = [v for v in range(num_days) if v not in closed_days]
            closed_day_constraints.append((idx, allowed_vehicles))
        
        # Track disjunction group for split nodes
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
        mandatory_node_indices.add(idx)  # Restaurants always mandatory

    # ---- STEP 4: Add auxiliary nodes (luggage, breaks) ----
    # Drop luggage (Day 1: Outbound → Hotel Day 1 to drop bags)
    if outbound.get("drop_luggage", False) and len(hotels) > 0:
        first_hotel = hotels[0]
        idx = _add_node(
            f"{first_hotel['name']} (Gửi đồ)",
            first_hotel["location"]["lat"], first_hotel["location"]["lng"],
            (480, 720), 30, "drop_luggage"
        )
        drop_luggage_info = (idx, 0)  # vehicle 0 = Day 1
        mandatory_node_indices.add(idx)

    # Pickup luggage (Last Day: Hotel → Return to pick up bags)
    if return_loc.get("pickup_luggage", False) and len(hotels) > 0:
        last_hotel = hotels[-1]
        idx = _add_node(
            f"{last_hotel['name']} (Lấy đồ)",
            last_hotel["location"]["lat"], last_hotel["location"]["lng"],
            (600, 1440), 30, "pickup_luggage"
        )
        pickup_luggage_info = (idx, num_days - 1)  # last vehicle
        mandatory_node_indices.add(idx)

    # Hotel breaks (nghỉ trưa giữa ngày)
    # hotel.day = X (0-based) → break happens on day X itself (same day)
    for hotel in hotels:
        if hotel.get("break_time_window"):
            break_day_vehicle = hotel["day"]  # rest on the SAME day
            if break_day_vehicle < num_days:
                idx = _add_node(
                    f"{hotel['name']} (Nghỉ trưa)",
                    hotel["location"]["lat"], hotel["location"]["lng"],
                    hotel["break_time_window"],
                    hotel.get("break_duration", 120),
                    "break"
                )
                break_nodes.append((idx, break_day_vehicle))
                mandatory_node_indices.add(idx)

    # ---- STEP 5: Auto-generate missing meals ----
    # Số bữa trưa cần = num_days, số bữa tối cần tùy vào return time
    num_lunch_needed = num_days
    num_dinner_needed = num_days
    
    # Nếu ngày cuối kết thúc sớm (trước 18h), không cần ăn tối
    return_tw = return_loc.get("time_window", (900, 1440))
    if return_tw[1] <= 1080:  # Về trước 18:00
        num_dinner_needed = num_days - 1
    
    # Thêm bữa trưa generic nếu thiếu
    while len(lunch_nodes) < num_lunch_needed:
        idx = _add_node(
            f"Ăn trưa (Tự chọn {len(lunch_nodes) + 1})",
            0, 0,  # Placeholder coords → sẽ dùng flat distance
            (660, 750),  # 11:00 - 12:30
            90, "generic_restaurant"
        )
        lunch_nodes.append(idx)
        mandatory_node_indices.add(idx)

    # Thêm bữa tối generic nếu thiếu
    while len(dinner_nodes) < num_dinner_needed:
        idx = _add_node(
            f"Ăn tối (Tự chọn {len(dinner_nodes) + 1})",
            0, 0,  # Placeholder coords
            (1080, 1320),  # 18:00 - 22:00
            90, "generic_restaurant"
        )
        dinner_nodes.append(idx)
        mandatory_node_indices.add(idx)
    
    # ---- Build vehicle meal capacities (per-day) ----
    vehicle_lunch_cap = [1] * num_days
    vehicle_dinner_cap = [1 if d < num_dinner_needed else 0 for d in range(num_days)]

    return {
        "nodes": nodes,
        "time_windows": time_windows,
        "service_times": service_times,
        "num_vehicles": num_days,
        "starts": starts,
        "ends": ends,
        "lunch_nodes": lunch_nodes,
        "dinner_nodes": dinner_nodes,
        "vehicle_lunch_cap": vehicle_lunch_cap,
        "vehicle_dinner_cap": vehicle_dinner_cap,
        "mandatory_node_indices": mandatory_node_indices,
        "closed_day_constraints": closed_day_constraints,
        "drop_luggage_info": drop_luggage_info,
        "pickup_luggage_info": pickup_luggage_info,
        "break_nodes": break_nodes,
        "disjunction_groups": disjunction_groups,
    }


# ============================================================================
# DISTANCE MATRIX
# ============================================================================

def _deduplicate_locations(nodes: list[dict]) -> tuple[list[tuple], dict]:
    """
    Tìm các tọa độ duy nhất, trả về mapping node_index → unique_loc_index.
    Nodes có lat=0, lng=0 (generic restaurants) sẽ được giữ riêng.
    """
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


def _fetch_distance_matrix_chunked(
    unique_locs: list[tuple],
    chunk_size: int = 25,
    use_api: bool = False,
) -> list[list[int]]:
    """
    Fetch travel time matrix using Routes API computeRouteMatrix.
    Supports up to 625 elements (25x25) per request.
    If use_api=False, uses Euclidean mock.
    """
    n = len(unique_locs)
    
    if not use_api or n == 0:
        # Mock Euclidean distance (minutes)
        matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    dist = math.hypot(
                        (unique_locs[i][0] - unique_locs[j][0]) * 111,  # lat → km
                        (unique_locs[i][1] - unique_locs[j][1]) * 111 * math.cos(math.radians(unique_locs[i][0]))
                    )
                    # Approx driving time: 30 km/h average in city
                    matrix[i][j] = max(5, int(dist / 30 * 60))
        return matrix
    
    # Routes API computeRouteMatrix — Essentials SKU
    # NOTE: Do NOT add routingPreference: "TRAFFIC_AWARE" or "TRAFFIC_AWARE_OPTIMAL"
    # as that upgrades to Pro SKU ($10/1000 elements instead of $5/1000).
    # Essentials SKU: travelMode only, no traffic → max 625 elements/request, $5/1000 elements.
    try:
        import httpx
        
        matrix = [[0] * n for _ in range(n)]
        total_elements = 0
        chunk_count = 0
        
        for i_start in range(0, n, chunk_size):
            i_end = min(i_start + chunk_size, n)
            
            for j_start in range(0, n, chunk_size):
                j_end = min(j_start + chunk_size, n)
                
                origins = [
                    {
                        "waypoint": {
                            "location": {
                                "latLng": {"latitude": unique_locs[i][0], "longitude": unique_locs[i][1]}
                            }
                        }
                    }
                    for i in range(i_start, i_end)
                ]
                
                destinations = [
                    {
                        "waypoint": {
                            "location": {
                                "latLng": {"latitude": unique_locs[j][0], "longitude": unique_locs[j][1]}
                            }
                        }
                    }
                    for j in range(j_start, j_end)
                ]
                
                num_elements = len(origins) * len(destinations)
                total_elements += num_elements
                chunk_count += 1
                
                body = {
                    "origins": origins,
                    "destinations": destinations,
                    "travelMode": "DRIVE",
                    # No routingPreference → Essentials SKU ($5/1000 elements)
                }
                
                logger.info(
                    f"[Routes API] Chunk #{chunk_count}: "
                    f"{len(origins)} origins × {len(destinations)} dests = {num_elements} elements "
                    f"(SKU: Essentials, travelMode: DRIVE)"
                )
                
                # resp = httpx.post(
                #     "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix",
                #     json=body,
                #     headers={
                #         "Content-Type": "application/json",
                #         "X-Goog-Api-Key": settings.GOOGLE_MAPS_API_KEY,
                #         "X-Goog-FieldMask": "originIndex,destinationIndex,duration,status,condition",
                #     },
                #     timeout=60.0,
                # )
                # resp.raise_for_status()
                # elements = resp.json()

                elements = ROUTE_MATRIX_MOCK

                logger.info(f"[Routes API] Response: {elements}")

                routes_found = 0
                for elem in elements:
                    oi = elem.get("originIndex", 0)
                    di = elem.get("destinationIndex", 0)
                    condition = elem.get("condition", "")
                    
                    if condition == "ROUTE_EXISTS":
                        dur_str = elem.get("duration", "0s")
                        dur_seconds = int(dur_str.rstrip("s")) if dur_str else 0
                        matrix[i_start + oi][j_start + di] = dur_seconds // 60
                        routes_found += 1
                    else:
                        matrix[i_start + oi][j_start + di] = 9999
     
        return matrix
    except Exception as e:
        logger.error(f"[Routes API] Error: {e}. Falling back to Euclidean.")
        return _fetch_distance_matrix_chunked(unique_locs, chunk_size, use_api=False)


def _build_distance_matrix(
    nodes: list[dict],
    use_api: bool = False,
    generic_distance: int = 15,
) -> list[list[int]]:
    """
    Builds the full NxN time matrix for all nodes.
    - Deduplicates real coordinates to minimize API calls.
    - Generic nodes (lat=0, lng=0) get a flat distance to all others.
    """
    n = len(nodes)
    unique_locs, node_to_unique, generic_nodes = _deduplicate_locations(nodes)
    
    # Fetch matrix for unique real locations
    unique_matrix = _fetch_distance_matrix_chunked(unique_locs, use_api=use_api)
    
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

def solve_vrp(
    locations: list[dict],
    use_api: bool = False,
    generic_distance: int = 15,
    time_limit_seconds: int = 3,
) -> dict:
    """
    Core VRP solver function.
    
    Args:
        locations: List of location dicts with type, name, location, etc.
        use_api: Whether to call Google Maps Routes API (False = Euclidean mock).
        generic_distance: Default travel time (minutes) for auto-generated restaurants.
        time_limit_seconds: Solver time limit.
    
    Returns:
        {
            "days": [
                {
                    "day": 1,
                    "stops": [
                        {"name": str, "arrival": str, "departure": str, "duration": int, "travel_to_next": int, "wait": int}
                    ]
                }
            ],
            "dropped": [str],       # Tên các địa điểm bị bỏ
            "objective": int,       # Solver objective value
        }
    """
    logger.info(f"Locations: {locations}")

    # ---- Step 1: Determine days & build nodes ----
    num_days = _determine_num_days(locations)
    data = _build_nodes(locations, num_days)
    
    # ---- Step 2: Build distance matrix + apply travel buffer ----
    raw_matrix = _build_distance_matrix(
        data["nodes"], use_api=use_api, generic_distance=generic_distance
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
    data["time_matrix"] = buffered_matrix      # Solver uses buffered
    data["raw_time_matrix"] = raw_matrix        # For display
    
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
    # time_dimension.SetGlobalSpanCostCoefficient(100)
    # Tổng thời gian hoạt động của cả 3 xe nhỏ nhất -> Tối ưu để giảm thời gian chờ + thời gian di chuyển
    time_dimension.SetSpanCostCoefficientForAllVehicles(100)
    # Slack Cost Penaly - Giảm thời gian chờ
    # time_dimension.SetSlackCostCoefficientForAllVehicles(50)
    
    # ---- Meal constraints (Lunch) ----
    if data["lunch_nodes"]:
        def lunch_callback(from_index):
            node = manager.IndexToNode(from_index)
            return 1 if node in data["lunch_nodes"] else 0
        
        lunch_cb = routing.RegisterUnaryTransitCallback(lunch_callback)
        routing.AddDimensionWithVehicleCapacity(
            lunch_cb, 0, data["vehicle_lunch_cap"], True, "Lunch"
        )
    
    # ---- Meal constraints (Dinner) ----
    if data["dinner_nodes"]:
        def dinner_callback(from_index):
            node = manager.IndexToNode(from_index)
            return 1 if node in data["dinner_nodes"] else 0
        
        dinner_cb = routing.RegisterUnaryTransitCallback(dinner_callback)
        routing.AddDimensionWithVehicleCapacity(
            dinner_cb, 0, data["vehicle_dinner_cap"], True, "Dinner"
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
    solver = routing.solver()
    
    # Drop luggage: force Start(day1) → drop_node
    if data["drop_luggage_info"]:
        node_idx, vehicle_idx = data["drop_luggage_info"]
        routing_idx = manager.NodeToIndex(node_idx)
        routing.SetAllowedVehiclesForIndex([vehicle_idx], routing_idx)
        solver.Add(routing.NextVar(routing.Start(vehicle_idx)) == routing_idx)
    
    # Pickup luggage: force pickup_node → End(day_last)
    if data["pickup_luggage_info"]:
        node_idx, vehicle_idx = data["pickup_luggage_info"]
        routing_idx = manager.NodeToIndex(node_idx)
        routing.SetAllowedVehiclesForIndex([vehicle_idx], routing_idx)
        solver.Add(routing.NextVar(routing_idx) == routing.End(vehicle_idx))
    
    # Break nodes: lock to specific day
    for node_idx, vehicle_idx in data["break_nodes"]:
        routing_idx = manager.NodeToIndex(node_idx)
        routing.SetAllowedVehiclesForIndex([vehicle_idx], routing_idx)
    
    # Closed day constraints
    for node_idx, allowed_vehicles in data["closed_day_constraints"]:
        routing_idx = manager.NodeToIndex(node_idx)
        routing.SetAllowedVehiclesForIndex(allowed_vehicles, routing_idx)
    
    # ---- Disjunction: grouped split nodes + individual droppable nodes ----
    penalty = 10000
    non_droppable = set(data["starts"]) | set(data["ends"]) | data["mandatory_node_indices"]
    handled_by_group = set()
    
    # Grouped disjunction for split attraction nodes
    for group_id, group_node_indices in data.get("disjunction_groups", {}).items():
        routing_indices = [int(manager.NodeToIndex(n)) for n in group_node_indices]
        # Check if any node in this group is must_visit (mandatory)
        any_mandatory = any(n in data["mandatory_node_indices"] for n in group_node_indices)
        if any_mandatory:
            # Must visit: exactly 1 of the group must appear (penalty = very high)
            routing.AddDisjunction(routing_indices, 100000)
        else:
            # Not must visit: all can be dropped (penalty = normal)
            routing.AddDisjunction(routing_indices, penalty)
        handled_by_group.update(group_node_indices)
    
    # Individual disjunction for non-grouped, non-mandatory nodes
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
            "message": "Không tìm được giải pháp. Kiểm tra lại khung giờ hoặc giảm số điểm.",
            "days": [],
            "dropped": [],
            "objective": -1,
        }
    
    # ---- Extract solution ----
    result_days = []
    for vehicle_id in range(data["num_vehicles"]):
        day_stops = []
        index = routing.Start(vehicle_id)
        
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
                theoretical = departure + buffered_travel
                actual = solution.Min(time_dimension.CumulVar(next_index))
                stop["wait"] = max(0, actual - theoretical)
            
            day_stops.append(stop)
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
            "wait": 0,
        })
        
        result_days.append({"day": vehicle_id, "stops": day_stops})
    
    # Find dropped nodes
    dropped = []
    for node in range(routing.Size()):
        if routing.IsStart(node) or routing.IsEnd(node):
            continue
        if solution.Value(routing.NextVar(node)) == node:
            real_node = manager.IndexToNode(node)
            dropped.append(data["nodes"][real_node]["name"])
    
    return {
        "error": False,
        "days": result_days,
        "dropped": dropped,
        "objective": solution.ObjectiveValue(),
    }


# ============================================================================
# PRETTY PRINT
# ============================================================================

def print_itinerary(result: dict):
    """In lịch trình ra console dạng bảng đẹp."""
    if result.get("error"):
        print(f"❌ Lỗi: {result.get('message', 'Không tìm được giải pháp')}")
        print(f"   Trạng thái Solver: {result.get('status')}")
        return
    
    print(f"✅ Đã tìm thấy lộ trình! Objective: {result['objective']}")
    
    for day_data in result["days"]:
        print(f"\n{'='*80}")
        print(f" LỊCH TRÌNH NGÀY {day_data['day']}:")
        print(f" {'ĐỊA ĐIỂM':<35} | {'GIỜ ĐẾN':<8} | {'THỜI GIAN':<10} | {'GIỜ ĐI':<8}")
        print("-" * 80)
        
        stops = day_data["stops"]
        for i, stop in enumerate(stops):
            if stop["duration"] > 0:
                activity = f"{stop['duration']}p"
            elif i == len(stops) - 1:
                activity = "Kết thúc"
            else:
                activity = "0p"
            
            dep = stop["departure"] if stop["departure"] else ""
            print(f" {stop['name']:<35} | {stop['arrival']:<8} | {activity:<10} | {dep:<8}")
            
            if i < len(stops) - 1 and stop.get("travel_to_next_buffered", stop["travel_to_next"]) > 0:
                travel = stop["travel_to_next"]
                buf = stop.get("buffer", 0)
                wait = stop["wait"]
                parts = [f"Di chuyển {travel}p"]
                if buf > 0:
                    parts.append(f"Buffer {buf}p")
                if wait > 0:
                    parts.append(f"Chờ {wait}p")
                print(f"   ... ({' + '.join(parts)}) ...")
    
    print("=" * 80)
    
    if result["dropped"]:
        print(f"\n❌ ĐỊA ĐIỂM BỊ BỎ QUA ({len(result['dropped'])} điểm):")
        for name in result["dropped"]:
            print(f"  - {name}")


# ============================================================================
# EXAMPLE: 3 ngày tại Hà Nội
# Nghỉ trưa đang hơi lỗi, ví dụ muốn nghỉ ngay ngày 1 ? Sau khi đi máy bay nghỉ luôn, Ngày cuối không nghỉ được trong khoảng nào vì checkout rồi
# Checkout ngày cuối rồi đi, = lấy đồ
# ============================================================================

if __name__ == "__main__":
    example_locations = [
        # --- Outbound ---
        {
            "type": "outbound",
            "name": "Sân bay Nội Bài",
            "location": {"lat": 21.2187, "lng": 105.8041},
            "time_window": (480, 540),  # 08:00 - 09:00
            "drop_luggage": True,
        },
        # --- Return ---
        {
            "type": "return",
            "name": "Sân bay Nội Bài",
            "location": {"lat": 21.2187, "lng": 105.8041},
            "time_window": (900, 1080),  # 15:00 - 18:00
            "pickup_luggage": True,
        },
        # --- Hotels ---
        {
            "type": "hotel",
            "name": "KS Phố Cổ",
            "location": {"lat": 21.0340, "lng": 105.8500},
            "day": 0,
            "checkin_time": (1020, 1440), # 17:00 - 24:00
            "checkout_time": (480, 480),
        },
        {
            "type": "hotel",
            "name": "KS Tây Hồ",
            "location": {"lat": 21.0650, "lng": 105.8200},
            "day": 1,
            "checkin_time": (1020, 1440),
            "checkout_time": (480, 480),
        },
        # --- Attractions ---
        {
            "type": "attraction",
            "name": "Lăng Bác",
            "location": {"lat": 21.0368, "lng": 105.8350},
            "time_window": (480, 690),
            "duration": 120,
            "closed_days": [2],  # Đóng cửa ngày 2 (0-based)
            "must_visit": True,
        },
        {
            "type": "attraction",
            "name": "Văn Miếu Quốc Tử Giám",
            "location": {"lat": 21.0275, "lng": 105.8365},
            "time_window": (480, 1020),
            "duration": 120,
            "must_visit": True,
        },
        {
            "type": "attraction",
            "name": "Hồ Hoàn Kiếm",
            "location": {"lat": 21.0285, "lng": 105.8523},
            "time_window": (420, 1320),
            "duration": 120,
        },
        {
            "type": "attraction",
            "name": "Chùa Trấn Quốc",
            "location": {"lat": 21.0478, "lng": 105.8366},
            "time_window": (480, 1080),
            "duration": 60,
        },
        {
            "type": "attraction",
            "name": "Hoàng Thành Thăng Long",
            "location": {"lat": 21.0359, "lng": 105.8400},
            "time_window": (480, 1020),
            "duration": 90,
        },
        {
            "type": "attraction",
            "name": "Làng gốm Bát Tràng",
            "location": {"lat": 21.0012, "lng": 105.9111},
            "time_window": (480, 1020),
            "duration": 180,
        },
        {
            "type": "attraction",
            "name": "Nhà hát Lớn Hà Nội",
            "location": {"lat": 21.0244, "lng": 105.8572},
            "time_window": (480, 1320),
            "duration": 90,
        },
        # --- Restaurants ---
        {
            "type": "restaurant",
            "name": "Bún Chả Hàng Mành",
            "location": {"lat": 21.0338, "lng": 105.8512},
            "time_window": (660, 810),
            "meal": "lunch",
            "duration": 90,
        },
        {
            "type": "restaurant",
            "name": "Phở Gia Truyền",
            "location": {"lat": 21.0325, "lng": 105.8480},
            "time_window": (660, 810),
            "meal": "lunch",
            "duration": 90,
        },
        {
            "type": "restaurant",
            "name": "Bún Rêu Cua",
            "location": {"lat": 21.0290, "lng": 105.8555},
            "time_window": (660, 810),
            "meal": "lunch",
            "duration": 90,
        },
        {
            "type": "restaurant",
            "name": "Chả Cá Lã Vọng",
            "location": {"lat": 21.0350, "lng": 105.8490},
            "time_window": (1080, 1320),
            "meal": "dinner",
            "duration": 90,
        },
        {
            "type": "restaurant",
            "name": "Phở Cuốn Ngũ Xã",
            "location": {"lat": 21.0450, "lng": 105.8420},
            "time_window": (1080, 1320),
            "meal": "dinner",
            "duration": 90,
        },
    ]
    
    print("🚀 Đang tính toán lộ trình tối ưu...")
    result = solve_vrp(example_locations, use_api=False, time_limit_seconds=5)
    print_itinerary(result)