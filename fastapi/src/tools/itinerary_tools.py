"""
"""

import json
import math
import logging
from typing import Any, Optional
from langchain_core.tools import tool

from src.tools.maps_tools import compute_route_matrix, LOCAL_TRANSPORT_MAP

logger = logging.getLogger(__name__)


# ============================================================================
# UTILITIES
# ============================================================================



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