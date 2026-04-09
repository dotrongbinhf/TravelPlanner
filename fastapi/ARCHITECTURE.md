# 🏗️ Multi-Agent Travel Planner — Architecture Map

> **Purpose**: Single source of truth for AI assistants. Read THIS file first before modifying any agent code.
> **Last updated**: 2026-04-06

---

## 1. Graph Topology

```
START → orchestrator → [conditional fan-out]
  ├─ (greeting/clarification/general) → END
  └─ (plan_creation) →  flight ──┐
                         hotel ───┤→ itinerary → restaurant ──┐→ synthesize → END
                         attraction┘              preparation ┘
```

- **Phase 1** (parallel): `flight` + `hotel` + `attraction` — fan-out from orchestrator
- **Fan-in**: All 3 → `itinerary`
- **Phase 2** (parallel): `restaurant` + `preparation` — fan-out from itinerary
- **Fan-in**: Both → `synthesize` → END

**File**: `src/agents/graph.py`
**Router**: `route_from_orchestrator()` — returns `["flight", "hotel", "attraction"]` or `END`
**Checkpointer**: `MemorySaver` (in-memory, keyed by `thread_id = conversation_id`)

---

## 2. State Schema

**File**: `src/agents/state.py` — `GraphState(TypedDict)`

| Field               | Type         | Reducer               | Description                                                               |
| ------------------- | ------------ | --------------------- | ------------------------------------------------------------------------- |
| `conversation_id`   | `str`        | —                     | Maps to MemorySaver thread_id                                             |
| `plan_id`           | `str`        | —                     | ID of the plan being created/modified                                     |
| `messages`          | `list`       | `add_messages`        | LangChain message history (auto-append)                                   |
| `pending_tasks`     | `list[str]`  | —                     | Agent task queue (set by orchestrator)                                    |
| `completed_tasks`   | `list[str]`  | —                     | Completed agent names                                                     |
| `user_context`      | `dict`       | —                     | Extracted user preferences                                                |
| `orchestrator_plan` | `dict`       | —                     | Full plan with per-agent context (see §3)                                 |
| `agent_outputs`     | `dict`       | `merge_agent_outputs` | Each agent writes `{agent_key: data}` — merge reducer for parallel safety |
| `final_response`    | `str`        | —                     | Final markdown text for user                                              |
| `structured_output` | `dict`       | —                     | Structured JSON for frontend UI                                           |
| `db_commands`       | `list[dict]` | —                     | DB operations for .NET backend                                            |
| `metadata`          | `dict`       | —                     | Flexible metadata                                                         |

---

## 3. Orchestrator Plan Structure

**File**: `src/agents/nodes/orchestrator_nonVRP.py`
**LLM**: `gemini-2.5-flash` (temp=0.3)
**Tools**: `tavily_search` (for researching unfamiliar destinations)

The orchestrator outputs `orchestrator_plan` with this structure:

```python
orchestrator_plan = {
    "intent": "plan_creation | plan_modification | greeting | clarification_needed | general",
    "tasks": ["attraction", "flight", "hotel", "restaurant"],  # which agents to run
    "plan_context": {
        "departure": "Ho Chi Minh City",
        "destination": "Hanoi",
        "start_date": "2026-03-17",
        "end_date": "2026-03-20",
        "num_days": 4,
        "adults": 2,
        "children": 0,
        "infants": 0,
        "children_ages": "5,8" or None,
        "interest": "history, culture",
        "pace": "relaxed | moderate | packed",
        "budget_level": "budget | moderate | luxury",
        "currency": "VND",
        "language": "vi",
        "local_transportation": "car | walking | motorbike | taxi",
        "mobility_plan": {
            "overview": "Detailed paragraph covering entire trip...",
            "departure_logistics": {
                "mode": "flight | coach | train | car | motorbike",
                "hub_name": "Bến xe Hà Giang" or None,       # null for flight/self-drive
                "hub_placeId": "ChIJ...",                      # resolved in Phase 2
                "estimated_travel_time": "6h",
                "estimated_cost": 500000,                      # numeric total for ALL travelers
                "estimated_cost_note": "250,000 VND/person × 2",
                "ready_time": "07:00",                         # when travelers are ready at destination
                "note": "Context about arrival"
            },
            "return_logistics": { ... },  # same structure
            "segments": [
                {
                    "segment_id": 0,
                    "segment_name": "Hà Giang → Quản Bạ → Yên Minh",
                    "attraction_days": [0],        # SOFT guidance for itinerary
                    "hotel_nights": [0],            # HARD constraint for hotel search
                    "hotel_search_area": "Yên Minh town center",
                    "attraction_search_area": "Dọc tuyến HG → QB → YM"
                }
            ]
        }
    },
    # Per-agent task contexts:
    "attraction": { "user_attractions_preferences": { "interest": [...], "must_visit": [...], ... } },
    "flight": { "infants_in_seat": 0, "infants_on_lap": 0, "user_flight_preferences": { ... } },
    "hotel": { "user_hotel_preferences": { "min_price": ..., "max_price": ..., ... } },
    "restaurant": { "user_cuisine_preferences": [...], "user_dietary_restrictions": [...], "notes": "..." },
}
```

### Key Design Decisions (Orchestrator)

- **No `travel_by` field** — mode is in `mobility_plan.departure_logistics.mode`
- **`estimated_cost`** is always a numeric total (integer), with `estimated_cost_note` for breakdown
- **When mode="flight"**: `departure_logistics = {"mode": "flight"}` only — Flight Agent handles all flight data
- **Day trips** to other regions: only when user explicitly asks, not proactively suggested
- **`must_visit`** in attraction preferences: only places the USER explicitly requested
- **Phase 2**: Non-flight hubs (coach/train) are resolved to placeIds via `_resolve_non_flight_hubs()`

---

## 4. Agent Map

### Phase 1 Agents (Parallel)

#### ✈️ Flight Agent

|                    |                                                                        |
| ------------------ | ---------------------------------------------------------------------- |
| **File**           | `src/agents/nodes/flight.py`                                           |
| **LLM**            | `gemini-3.1-flash-lite-preview` (temp=0.5)                             |
| **Tools**          | `search_airports`, `search_flights` (from `src/tools/dotnet_tools.py`) |
| **Reads**          | `orchestrator_plan.plan_context`, `orchestrator_plan.flight`           |
| **Writes**         | `agent_outputs.flight_agent`                                           |
| **Max iterations** | 10                                                                     |

**Output schema** (`agent_outputs.flight_agent`):

```python
{
    "type": "round_trip | one_way",
    "directions": "both | outbound_only | return_only",
    "outbound_flights_found": True,
    "recommend_outbound_flight": {
        "flight_number": "VN 240",
        "departure_time": "07:00",
        "departure_airport_name": "Tan Son Nhat International Airport",
        "departure_airport_placeId": "ChIJ...",  # resolved in Phase 2
        "arrival_time": "09:10",
        "arrival_airport_name": "Noi Bai International Airport",
        "arrival_airport_placeId": "ChIJ...",    # resolved in Phase 2
    },
    "recommend_outbound_note": "Why this flight was chosen...",
    "return_flights_found": True,
    "recommend_return_flight": { ... },
    "recommend_return_note": "...",
    "totalPrice": 5200000,  # extracted programmatically from tool_logs
    "tools": [...]          # raw tool call logs (for price extraction)
}
```

**Key behaviors**:

- Deduplicates airport resolution (2 unique airports, not 4)
- `_find_price_for_flight()`: searches tool_logs in **REVERSE** order, case-insensitive keys, unwraps `data` envelope
- `_extract_total_price()`: sums outbound + return prices
- Round-trip fallback: if return search fails → retry with 2nd outbound → fall back to one-way double search

#### 🏨 Hotel Agent

|                    |                                                             |
| ------------------ | ----------------------------------------------------------- |
| **File**           | `src/agents/nodes/hotel.py`                                 |
| **LLM**            | `gemini-3.1-flash-lite-preview` (temp=0.5)                  |
| **Tools**          | `search_hotels` (from `src/tools/dotnet_tools.py`)          |
| **Reads**          | `orchestrator_plan.plan_context`, `orchestrator_plan.hotel` |
| **Writes**         | `agent_outputs.hotel_agent`                                 |
| **Max iterations** | 5                                                           |

**Output schema** (`agent_outputs.hotel_agent`):

```python
{
    "segments": [
        {
            "segment_name": "Central Hanoi",
            "recommend_hotel_name": "Hanoi La Siesta Hotel",
            "recommend_hotel_placeId": "ChIJ...",  # resolved in Phase 2
            "totalRate": 3600000,                   # total for ALL nights
            "check_in": "2026-03-17",
            "check_out": "2026-03-20",
            "recommend_note": "Why this hotel..."
        }
    ],
    "tools": [...]
}
```

**Key behaviors**:

- Searches per segment (multi-segment → multiple search_hotels calls)
- Hotel names resolved in parallel via `asyncio.gather`
- `hotel_nights` from mobility_plan segments are HARD constraints (specific dates)

#### 🏛️ Attraction Agent

|                    |                                                                  |
| ------------------ | ---------------------------------------------------------------- |
| **File**           | `src/agents/nodes/attraction.py`                                 |
| **LLM**            | `gemini-2.5-flash` (temp=0.5)                                    |
| **Tools**          | `tavily_search` (from `src/tools/search_tools.py`)               |
| **Reads**          | `orchestrator_plan.plan_context`, `orchestrator_plan.attraction` |
| **Writes**         | `agent_outputs.attraction_agent`                                 |
| **Max iterations** | 3                                                                |

**Output schema** (`agent_outputs.attraction_agent`):

```python
{
    "segments": [
        {
            "segment_name": "Central Hanoi",
            "days": [0, 1, 2, 3],
            "attractions": [
                {
                    "name": "Hoan Kiem Lake",
                    "placeId": "ChIJ...",         # resolved via LLM-verified pipeline
                    "must_visit": False,
                    "estimated_entrance_fee": {"total": 0, "note": "Free"},
                    "includes": [
                        {"name": "Ngoc Son Temple", "placeId": "ChIJ...", "estimated_entrance_fee": {...}}
                    ],
                    "notes": "Includes the iconic red bridge..."
                }
            ]
        }
    ],
    "tools": [...]
}
```

**Key behaviors**:

- Uses LLM-verified place resolution (`src/services/place_resolution_llm.py`)
- Generates names in the language specified by `plan_context.language`
- `must_visit` = only places user explicitly requested
- `includes` = sub-attractions within/adjacent to main attraction
- `estimated_entrance_fee.total` = total for ALL travelers

---

### Sequential: Itinerary

#### 📅 Itinerary Agent

|             |                                                              |
| ----------- | ------------------------------------------------------------ |
| **File**    | `src/agents/nodes/itinerary_nonVRP.py`                       |
| **Service** | `src/services/itinerary_builder_nonVRP.py`                   |
| **LLM**     | `gemini-2.5-flash` (temp=0.3)                                |
| **Reads**   | ALL Phase 1 agent_outputs + `orchestrator_plan.plan_context` |
| **Writes**  | `agent_outputs.itinerary_agent`                              |

**Pipeline** (in `itinerary_builder_nonVRP.py`):

1. `extract_place_names()` — collect place names from flight/hotel/attraction outputs
2. `resolve_all_places()` — resolve names to placeIds + get openHours (uses pre-resolved placeIds when available)
3. `build_distance_matrix()` — Routes API for travel times between all places
4. `build_attractions_info()` — format opening hours per day, includes, entrance fees
5. `build_schedule_constraints()` — day 0 arrival, last day deadline, hotel check-in/out, luggage, midday rest
6. `_build_scheduling_prompt()` → send to LLM for scheduling

**Output schema** (`agent_outputs.itinerary_agent`):

```python
{
    "days": [
        {
            "day": 0,
            "date": "2026-03-17",
            "stops": [
                {"time": "09:30", "type": "attraction", "name": "Hoan Kiem Lake", "duration_minutes": 90, ...},
                {"time": "12:00", "type": "lunch", "name": "Lunch break", ...},
            ]
        }
    ],
    "dropped": ["Place X"],           # attractions that didn't fit
    "has_violations": False,
    "violations": [],
    "resolved_places": {...},         # internal — full resolved data
    "resolved_places_count": 15,
    "total_places_count": 17
}
```

**Key design decisions**:

- No `suggested_duration_minutes` default — LLM estimates duration based on attraction knowledge
- `attraction_days` are SOFT guidance — itinerary can flexibly assign across segments
- `hotel_nights` are HARD constraints — hotel is already booked for specific dates
- Post-validation: checks for gap/overlap violations
- Retry mechanism: LLM gets violation feedback and can re-schedule

---

### Phase 2 Agents (Parallel)

#### 🍜 Restaurant Agent

|            |                                                                                                   |
| ---------- | ------------------------------------------------------------------------------------------------- |
| **File**   | `src/agents/nodes/restaurant.py`                                                                  |
| **LLM**    | `gemini-2.5-flash` (temp=0.5)                                                                     |
| **Tools**  | `tavily_search`                                                                                   |
| **Reads**  | `agent_outputs.itinerary_agent`, `orchestrator_plan.plan_context`, `orchestrator_plan.restaurant` |
| **Writes** | `agent_outputs.restaurant_agent`                                                                  |

**Output**: `meals[]` with name, day, meal_type, estimated_cost_total, note

#### 🎒 Preparation Agent

|            |                                                                   |
| ---------- | ----------------------------------------------------------------- |
| **File**   | `src/agents/nodes/preparation.py`                                 |
| **LLM**    | `gemini-2.5-flash` (temp=0.5)                                     |
| **Tools**  | `tavily_search`                                                   |
| **Reads**  | `agent_outputs.itinerary_agent`, `orchestrator_plan.plan_context` |
| **Writes** | `agent_outputs.preparation_agent`                                 |

**Output**: `budget` (LOCAL transport, activities, shopping, other — NOT flight/hotel/departure transport), `packing_lists`, `notes`, `weather`

**Key**: Preparation does NOT estimate departure-to-destination transport costs — those come from `mobility_plan.departure_logistics.estimated_cost`

---

### Final: Synthesize

#### 📝 Synthesize Agent

|            |                                                                   |
| ---------- | ----------------------------------------------------------------- |
| **File**   | `src/agents/nodes/synthesize.py`                                  |
| **LLM**    | `gemini-3.1-flash-lite-preview` (temp=0.5, streaming)             |
| **Reads**  | ALL `agent_outputs` (curated), `plan_context`, `aggregated_costs` |
| **Writes** | `final_response`, `structured_output`, `db_commands`              |

**Key behaviors**:

- Uses `_build_curated_context()` — cherry-picks ONLY needed fields per agent (NOT raw dumps)
- Calls `aggregate_all_costs()` from `src/services/cost_aggregator.py`
- Calls `build_apply_data()` from `src/services/apply_data_builder.py` for frontend
- Only sends 1 `HumanMessage` (user's original request) — no conversation history

**Curated fields per agent** (what Synthesize LLM sees):

| Agent        | Fields included                                                        |
| ------------ | ---------------------------------------------------------------------- |
| Flight       | `recommend_outbound/return_flight`, `totalPrice`, `type`, notes        |
| Hotel        | `recommend_hotel_name`, `totalRate`, `check_in/out`, notes per segment |
| Itinerary    | `days`, `dropped`                                                      |
| Restaurant   | `name`, `day`, `meal_type`, `estimated_cost_total`, note per meal      |
| Preparation  | `budget`, `packing_lists`, `notes`, `weather`                          |
| Plan Context | Essential trip info + `mobility_plan.overview`                         |
| Costs        | Full `aggregated_costs`                                                |

---

## 5. Services

| Service                  | File                                       | Purpose                                                                                                   |
| ------------------------ | ------------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| **Place Resolver**       | `src/services/place_resolver.py`           | Simple Text Search → DB lookup. Used by Hotel & Flight agents.                                            |
| **LLM Place Resolution** | `src/services/place_resolution_llm.py`     | LLM-verified resolution with candidate ranking. Used by Attraction agent.                                 |
| **Itinerary Builder**    | `src/services/itinerary_builder_nonVRP.py` | 6-step pipeline: extract → resolve → distance → hours → constraints → prompt                              |
| **Cost Aggregator**      | `src/services/cost_aggregator.py`          | Aggregates costs from all agents. Categories: flights, hotels, attractions, restaurants, transport, other |
| **Apply Data Builder**   | `src/services/apply_data_builder.py`       | Converts agent_outputs → normalized format for frontend .NET Apply endpoint                               |
| **DotNet Client**        | `src/services/dotnet_client.py`            | HTTP client for .NET API. **Returns `{success, data}` envelope** — must unwrap!                           |

---

## 6. Tools

| Tool                         | File                           | Used by                                           |
| ---------------------------- | ------------------------------ | ------------------------------------------------- |
| `search_airports`            | `src/tools/dotnet_tools.py`    | Flight Agent                                      |
| `search_flights`             | `src/tools/dotnet_tools.py`    | Flight Agent                                      |
| `search_hotels`              | `src/tools/dotnet_tools.py`    | Hotel Agent                                       |
| `get_place_from_db`          | `src/tools/dotnet_tools.py`    | Place Resolver, Itinerary Builder                 |
| `places_text_search_id_only` | `src/tools/maps_tools.py`      | Place Resolver                                    |
| `tavily_search`              | `src/tools/search_tools.py`    | Orchestrator, Attraction, Restaurant, Preparation |
| `_build_distance_matrix`     | `src/tools/itinerary_tools.py` | Itinerary Builder                                 |

---

## 7. Utils & ReAct Loop

**File**: `src/agents/nodes/utils.py`

### `_run_agent_with_tools(llm, messages, tools, max_iterations, agent_name)`

- Standard ReAct loop: LLM → tool calls → LLM → ... → final JSON
- **Parallel tool execution**: When LLM emits multiple tool calls, executes via `asyncio.gather`
- **Tool result truncation**: `ToolMessage.content` capped at 4000 chars (full result in `tool_logs`)
- Returns `(final_llm_result, tool_logs)`

### Other helpers

- `_extract_json(text)` — extracts JSON from LLM response (handles ```json, lists, nested)
- `_get_latest_user_message(state)` — gets last HumanMessage from state
- `_get_conversation_context(state, max_messages=10)` — builds conversation history

## 8. Entry Point & WebSocket

**File**: `src/api/routes/websocket.py`
**Endpoint**: `ws://host:port/ws/agent/{conversation_id}`

### Flow

1. Client sends: `{"message": "...", "history": [...], "plan_id": "..."}`
2. Server checks MemorySaver for existing state
3. If no state + history provided → inject history (with **dedup check**: last history msg != current message)
4. Runs `compiled_graph.astream_events(graph_input, config, version="v2")`
5. Streams `AgentEvent` objects: `AGENT_START`, `AGENT_END`, `TEXT_CHUNK`, `STRUCTURED_DATA`, `WORKFLOW_COMPLETE`

---

## 9. Key Patterns & Decisions

### Place Resolution Strategy

- **Attraction**: LLM-verified (`place_resolution_llm.py`) — candidate ranking with confidence
- **Hotel/Flight**: Simple Text Search → DB (`place_resolver.py`)
- **Transport Hubs**: LLM-verified, resolved in orchestrator Phase 2 (`_resolve_non_flight_hubs`)
- **Pre-resolved placeIds**: Itinerary builder uses pre-resolved placeIds when available (skips re-search)

### Cost Aggregation

- Flight/Hotel: from `agent_outputs`
- Attractions: entrance fees from attraction agent
- Transport (non-flight): from `mobility_plan.departure/return_logistics.estimated_cost`
- Other: from preparation agent's `budget`
- **Preparation agent does NOT estimate departure-to-destination transport** (handled by mobility_plan)

### Token Optimization

- **ToolMessage truncation**: 4000 char cap in `_run_agent_with_tools` (full data in `tool_logs`)
- **Synthesize**: curated input only (not raw dumps) via `_build_curated_context()`
- **No conversation history** in Synthesize — only 1 user message + system prompt with curated data

### Flight Price Extraction (`_find_price_for_flight`)

- Searches tool_logs in **REVERSE order** (newest first — important for fallback retries)
- **Case-insensitive** key matching (handles both PascalCase and camelCase from .NET)
- **Unwraps** `{success, data}` envelope from dotnet_client

### .NET API Envelope

- `dotnet_client.py` wraps ALL API responses in `{success: bool, data: {...}}`
- **ALWAYS unwrap** `output.get("data", output)` before accessing actual data

---

## 10. File Tree (Active — excludes OR_Tool_Agents legacy)

```
src/
├── agents/
│   ├── graph.py                    # LangGraph StateGraph + routing
│   ├── state.py                    # GraphState TypedDict + merge reducer
│   └── nodes/
│       ├── __init__.py             # Re-exports all node functions
│       ├── utils.py                # LLM instances, _run_agent_with_tools, helpers
│       ├── orchestrator_nonVRP.py  # Orchestrator (prompt + plan + hub resolution)
│       ├── flight.py               # Flight Agent (search + price extraction + airport resolution)
│       ├── hotel.py                # Hotel Agent (search + hotel resolution)
│       ├── attraction.py           # Attraction Agent (search + LLM-verified resolution)
│       ├── itinerary_nonVRP.py     # Itinerary Agent (LLM scheduling + validation)
│       ├── restaurant.py           # Restaurant Agent (meal recommendations)
│       ├── preparation.py          # Preparation Agent (budget/packing/notes)
│       ├── synthesize.py           # Synthesize Agent (curated context → final response)
│       └── OR_Tool_Agents/         # ⚠️ LEGACY — not used in current graph
│
├── services/
│   ├── place_resolver.py           # Simple place resolution (hotel/flight)
│   ├── place_resolution_llm.py     # LLM-verified place resolution (attractions)
│   ├── itinerary_builder_nonVRP.py # 6-step itinerary pipeline
│   ├── cost_aggregator.py          # Cost aggregation from all agents
│   ├── apply_data_builder.py       # Frontend data normalization
│   ├── dotnet_client.py            # .NET API HTTP client (⚠️ returns {success,data} envelope)
│   └── OR_Tool_Agents/             # ⚠️ LEGACY
│
├── tools/
│   ├── dotnet_tools.py             # search_flights, search_hotels, search_airports, get_place_from_db
│   ├── maps_tools.py               # places_text_search_id_only, distance matrix
│   ├── search_tools.py             # tavily_search
│   ├── itinerary_tools.py          # _build_distance_matrix
│   └── place_resolver.py           # Tool wrapper for place resolution
│
├── api/routes/
│   └── websocket.py                # WebSocket endpoint + event streaming
│
├── config.py                       # Settings (API keys, etc.)
└── main.py                         # FastAPI app entry point
```
