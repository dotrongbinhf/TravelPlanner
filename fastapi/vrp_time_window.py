#!/usr/bin/env python3
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def minutes_to_time(minutes):
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours:02d}:{mins:02d}"

# [START data_model]
def create_data_model():
    data = {}
    
    # 0: Sân bay (Start)
    # 8: Khách sạn (End)
    
    # 1. TIME WINDOWS (Nới lỏng nhẹ một chút để đảm bảo có nghiệm)
    data["time_windows"] = [
        (480, 720),   # 0. Sân bay: Đón từ 8:00 - 12:00
        (420, 1260),  # 1. Cafe
        (450, 1020),  # 2. Thác
        (660, 900),   # 3. Ăn trưa (11:00 - 15:00) -> Nới rộng để dễ xếp lịch
        (420, 1020),  # 4. Dinh III
        (420, 1080),  # 5. Chùa
        (420, 1080),  # 6. Vườn Hoa
        (1080, 1320), # 7. Ăn tối (18:00 - 22:00)
        (0, 1440),    # 8. Khách sạn (End)
    ]

    # 2. SERVICE TIMES
    data["service_times"] = [15, 60, 90, 60, 60, 45, 45, 90, 0]

    # 3. TIME MATRIX
    data["time_matrix"] = [
        [0,  40, 30, 45, 45, 60, 55, 45, 40], # 0
        [40, 0,  20, 15, 20, 30, 25, 15, 10], # 1
        [30, 20, 0,  20, 15, 45, 40, 20, 15], # 2
        [45, 15, 20, 0,  15, 35, 30, 10, 5],  # 3
        [45, 20, 15, 15, 0,  40, 35, 15, 10], # 4
        [60, 30, 45, 35, 40, 0,  10, 35, 30], # 5
        [55, 25, 40, 30, 35, 10, 0,  30, 25], # 6
        [45, 15, 20, 10, 15, 35, 30, 0,  5],  # 7
        [40, 10, 15, 5,  10, 30, 25, 5,  0],  # 8
    ]

    data["num_vehicles"] = 1
    data["starts"] = [0]
    data["ends"] = [8]
    return data
# [END data_model]

def main():
    data = create_data_model()

    manager = pywrapcp.RoutingIndexManager(
        len(data["time_matrix"]), 
        data["num_vehicles"], 
        data["starts"], 
        data["ends"]
    )
    routing = pywrapcp.RoutingModel(manager)

    # --- CALLBACK TÍNH THỜI GIAN ---
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # Thời gian tiêu tốn = Đi đường + Chơi tại điểm cũ
        return data["time_matrix"][from_node][to_node] + data["service_times"][from_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # --- ADD DIMENSION ---
    time = "Time"
    routing.AddDimension(
        transit_callback_index,
        1440,  # Slack (Cho phép chờ đợi thoải mái)
        1440,  # Horizon (Giới hạn trong 24h)
        False, # force_start_cumul_to_zero
        time,
    )
    time_dimension = routing.GetDimensionOrDie(time)

    # --- SET TIME WINDOWS ---
    for location_idx, time_window in enumerate(data["time_windows"]):
        if location_idx in data["starts"] or location_idx in data["ends"]:
            continue
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])

    # Time Window cho Start & End
    start_index = routing.Start(0)
    end_index = routing.End(0)
    
    start_window = data["time_windows"][data["starts"][0]]
    end_window = data["time_windows"][data["ends"][0]]
    
    time_dimension.CumulVar(start_index).SetRange(start_window[0], start_window[1])
    time_dimension.CumulVar(end_index).SetRange(end_window[0], end_window[1])

    # --- CHIẾN LƯỢC TÌM KIẾM (QUAN TRỌNG NHẤT) ---
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    
    # THAY ĐỔI 1: Dùng PARALLEL_CHEAPEST_INSERTION thay vì PATH_CHEAPEST_ARC
    # Chiến lược này linh hoạt hơn khi có Time Window phức tạp.
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    
    # THAY ĐỔI 2: Sử dụng Guided Local Search để tối ưu hóa thêm
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = 2 # Cho nó suy nghĩ 5 giây
    # search_parameters.log_search = True # Bật log nếu muốn xem quá trình giải

    print("🚀 Đang tính toán lộ trình tối ưu...")
    solution = routing.SolveWithParameters(search_parameters)

    # --- IN KẾT QUẢ ---
    if solution:
        print(f"✅ Đã tìm thấy lộ trình! Tổng chi phí thời gian: {solution.ObjectiveValue()} phút")
        index = routing.Start(0)
        
        names = [
            "Sân bay Liên Khương", "Cafe Túi Mơ To", "Thác Datanla", 
            "Quán Lẩu Gà (Ăn trưa)", "Dinh III", "Chùa Ve Chai", 
            "Vườn Hoa Cẩm Tú Cầu", "Quán Nướng (Ăn tối)", "Khách sạn Trung Tâm"
        ]
        
        print("-" * 60)
        print(f"{'ĐỊA ĐIỂM':<25} | {'GIỜ ĐẾN':<10} | {'HOẠT ĐỘNG':<10} | {'GIỜ ĐI':<10}")
        print("-" * 60)

        while not routing.IsEnd(index):
            time_var = time_dimension.CumulVar(index)
            node_index = manager.IndexToNode(index)
            
            arrival_val = solution.Min(time_var)
            service_duration = data["service_times"][node_index]
            departure_val = arrival_val + service_duration
            
            print(f"{names[node_index]:<25} | {minutes_to_time(arrival_val):<10} | {service_duration}p{' ':<7} | {minutes_to_time(departure_val):<10}")
            
            # Kiểm tra xem có cần chờ không (Slack)
            next_index = solution.Value(routing.NextVar(index))
            if not routing.IsEnd(next_index):
                # Tính thời gian đến điểm tiếp theo theo lý thuyết (không chờ)
                travel_time = data["time_matrix"][node_index][manager.IndexToNode(next_index)]
                theoretical_arrival = departure_val + travel_time
                
                # Thời gian đến thực tế do Solver tính
                next_time_var = time_dimension.CumulVar(next_index)
                actual_arrival = solution.Min(next_time_var)
                
                waiting_time = actual_arrival - theoretical_arrival
                if waiting_time > 0:
                    print(f"   ... (Di chuyển {travel_time}p + Chờ {waiting_time}p để đúng giờ mở cửa) ...")
                else:
                    print(f"   ... (Di chuyển {travel_time}p) ...")

            index = next_index
            
        # In điểm cuối
        time_var = time_dimension.CumulVar(index)
        node_index = manager.IndexToNode(index)
        print(f"{names[node_index]:<25} | {minutes_to_time(solution.Min(time_var)):<10} | {'Kết thúc':<10} |")
        print("-" * 60)
        
    else:
        print("❌ Vẫn không tìm thấy giải pháp!")
        print("Trạng thái Solver:", routing.status())
        print("Lời khuyên: Hãy kiểm tra lại Giờ Ăn Trưa (Node 3) hoặc Ăn Tối (Node 7).")
        print("Ví dụ: Nếu đi hết các điểm mất 4 tiếng mà bắt ăn trưa lúc 11h nhưng xuất phát lúc 8h thì có thể không kịp.")

if __name__ == "__main__":
    main()