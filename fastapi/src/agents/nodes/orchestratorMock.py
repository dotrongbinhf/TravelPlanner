Orchestrator_Mock = """```json
{
  "intent": "plan_creation",
  "direct_response": null,
  "plan_context": {
    "departure": "Ho Chi Minh City",
    "travel_by": "flight",
    "mobility_plan": "Depart from Ho Chi Minh City in the morning and arrive in Hanoi before noon of the first day. Depart from Hanoi in the afternoon of the last day to return to Ho Chi Minh City.",
    "destination": "Hanoi",
    "local_transportation": "car",
    "start_date": "2026-03-27",
    "end_date": "2026-03-30",
    "num_days": 4,
    "adults": 2,
    "children": 1,
    "infants": 1,
    "children_ages": "5,1",
    "interest": "history, culture, food, cuisine",
    "pace": "moderate",
    "budget_level": "moderate",
    "currency": "VND",
    "geographic_type": "centralized"
  },
  "tasks": {
    "attraction": {
      "segments": [
        {
          "segment_name": "Central Hanoi",
          "days": [1, 2, 3, 4],
          "area_description": "Central Hanoi districts including Hoàn Kiếm, Ba Đình, and surrounding areas.",
          "route_stops": null
        }
      ],
      "notes": "Day 1 is arrival day. Day 4 is departure day.",
      "user_attractions_preferences": {
        "interest": ["history", "cultural"],
        "must_visit": [],
        "to_avoid": [],
        "notes": null
      }
    },
    "flight": {
      "departure_airport_hint": "Tân Sơn Nhất (SGN)",
      "destination_airport_hint": "Nội Bài (HAN)",
      "infants_in_seat": 0,
      "infants_on_lap": 1,
      "user_flight_preferences": {
        "type": "round_trip",
        "travel_class": "economy",
        "max_price": null,
        "outbound_times": null,
        "return_times": null,
        "note": null
      }
    },
    "hotel": {
      "user_hotel_preferences": {
        "min_price": null,
        "max_price": null,
        "notes": null
      },
      "hotel_segments": [
        {
          "segment_name": "Central Hanoi Stay",
          "search_area": "Hoàn Kiếm district or Old Quarter, Hanoi",
          "check_in": "2026-03-27",
          "check_out": "2026-03-30",
          "nights": 3,
          "notes": "Convenient access to historical sites, cultural attractions, and local food."
        }
      ]
    },
    "restaurant": {
      "user_cuisine_preferences": ["Vietnamese cuisine", "local street food"],
      "user_dietary_restrictions": [],
      "notes": "Focus on authentic local cuisine in Hanoi."
    }
  }
}
```"""


Orchestrator_Mock_HG = """```json
{
  "intent": "plan_creation",
  "direct_response": null,
  "plan_context": {
    "departure": "Hanoi",
    "travel_by": "coach | motobike",
    "mobility_plan": {
      "plan": "Travel by coach from Hanoi to Ha Giang city early morning on Day 1. Upon arrival, pick up rented motorbikes and begin the loop, exploring scenic routes and attractions. Each day involves significant motorbike travel between towns. Overnight stays will be in different towns along the loop. On the last day, complete the loop, return motorbikes in Ha Giang city, and take an afternoon/evening coach back to Hanoi.",
      "midday_rest_days": null,
      "souvenir_shopping": false
    },
    "transport_hubs": {
      "outbound_departure": "My Dinh Bus Station, Hanoi",
      "outbound_arrival": "Ha Giang Bus Station",
      "return_departure": "Ha Giang Bus Station",
      "return_arrival": "My Dinh Bus Station, Hanoi",
      "outbound_time": "06:00",
      "return_time": "15:00"
    },
    "destination": "Ha Giang",
    "local_transportation": "motobike",
    "start_date": "2026-04-01",
    "end_date": "2026-04-03",
    "num_days": 3,
    "adults": 4,
    "children": 0,
    "infants": 0,
    "children_ages": null,
    "interest": "scenic views, nature, ethnic culture",
    "pace": "moderate",
    "budget_level": "moderate",
    "currency": "VND",
    "geographic_type": "road_trip"
  },
  "tasks": {
    "attraction": {
      "segments": [
        {
          "segment_name": "Day 1: Ha Giang City to Yên Minh",
          "days": [1],
          "area_description": "Ha Giang City, Quản Bạ Pass, Heaven's Gate, Quản Bạ Twin Mountains, Lùng Tám weaving village, Yên Minh town."
        },
        {
          "segment_name": "Day 2: Yên Minh to Mèo Vạc",
          "days": [2],
          "area_description": "Yên Minh, Đồng Văn Karst Plateau Geopark, Phố Cáo, Sủng Là (Pao's House), Dinh Vua Mèo (King's Palace), Đồng Văn Old Town, Mã Pì Lèng Pass, Nho Quế River, Mèo Vạc town."
        },
        {
          "segment_name": "Day 3: Mèo Vạc to Ha Giang City",
          "days": [3],
          "area_description": "Mèo Vạc, scenic route back towards Ha Giang City (e.g., through Mậu Duệ, Du Già if time permits, or direct route 4C), Ha Giang City."
        }
      ],
      "notes": "Focus on scenic viewpoints, ethnic minority villages, and cultural sites along the Ha Giang Loop. Day 1 is arrival and start of the loop. Day 3 is completion of the loop and departure.",
      "user_attractions_preferences": {
        "interest": ["scenic views", "nature", "ethnic culture"],
        "must_visit": [],
        "to_avoid": [],
        "notes": null
      }
    },
    "flight": null,
    "hotel": {
      "user_hotel_preferences": {
        "min_price": null,
        "max_price": null,
        "notes": "Moderate budget, comfortable and clean guesthouses/homestays suitable for a road trip."
      },
      "hotel_segments": [
        {
          "segment_name": "Yên Minh Stay",
          "search_area": "Yên Minh town, Ha Giang",
          "check_in": "2026-04-01",
          "check_out": "2026-04-02",
          "nights": 1,
          "notes": "First overnight stop on the Ha Giang loop."
        },
        {
          "segment_name": "Mèo Vạc Stay",
          "search_area": "Mèo Vạc town, Ha Giang",
          "check_in": "2026-04-02",
          "check_out": "2026-04-03",
          "nights": 1,
          "notes": "Second overnight stop, after exploring Đồng Văn and Mã Pì Lèng."
        }
      ]
    },
    "restaurant": {
      "user_cuisine_preferences": ["local Vietnamese cuisine", "ethnic minority dishes"],
      "user_dietary_restrictions": [],
      "notes": "Focus on local specialties of Ha Giang, such as 'thắng cố', 'cháo ấu tẩu', 'bánh cuốn Đồng Văn'."
    }
  }
}
```"""