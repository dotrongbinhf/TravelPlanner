import os
import re

base_dir = r"d:\.Current_Study\GraduationThesis\fastapi\src\agents"
backup_dir = os.path.join(base_dir, "nodes_backup")
nodes_dir = os.path.join(base_dir, "nodes")

if not os.path.exists(nodes_dir):
    os.makedirs(nodes_dir)

with open(os.path.join(backup_dir, "nodes.py"), "r", encoding="utf-8") as f:
    nodes_code = f.read()

with open(os.path.join(backup_dir, "prompts.py"), "r", encoding="utf-8") as f:
    prompts_code = f.read()

# Extract prompts
prompts = {}
for match in re.finditer(r"^([A-Z_]+_SYSTEM)\s*=\s*\"\"\"(.*?)\"\"\"", prompts_code, flags=re.MULTILINE | re.DOTALL):
    name, content = match.groups()
    prompts[name] = f'{name} = """{content}"""\n'

# Extract nodes content
# 0: header, 1: Orchestrator, 2: Attraction, 3: Flight, 4: Hotel, 5: Restaurant, 6: Itinerary, 7: Preparation, 8: Synthesize
parts = re.split(r"# ============================================================\n# \d+\. .*?\n# ============================================================\n", nodes_code)

header_and_utils = parts[0]
llm_parts = header_and_utils.split("# ============================================================\n# LLM Instances\n# ============================================================\n")
llm_and_helpers = llm_parts[1] if len(llm_parts) > 1 else ""

# Write utils.py
utils_content = f"""\"\"\"
Common utilities and LLM instances for the LangGraph multi-agent travel planner.
\"\"\"

import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agents.state import GraphState
from src.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# LLM Instances
# ============================================================
{llm_and_helpers}"""

with open(os.path.join(nodes_dir, "utils.py"), "w", encoding="utf-8") as f:
    f.write(utils_content)


agents = [
    {
        "name": "orchestrator",
        "prompt_var": "ORCHESTRATOR_SYSTEM",
        "index": 1,
        "imports": "from src.agents.nodes.utils import _extract_json, _get_latest_user_message, _get_conversation_context, llm_fast",
        "tools": ""
    },
    {
        "name": "attraction",
        "prompt_var": "ATTRACTION_AGENT_SYSTEM",
        "index": 2,
        "imports": "from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent, llm_fast",
        "tools": "from src.tools.search_tools import tavily_search\nfrom src.tools.place_resolver import resolve_place"
    },
    {
        "name": "flight",
        "prompt_var": "FLIGHT_AGENT_SYSTEM",
        "index": 3,
        "imports": "from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent",
        "tools": "from src.tools.dotnet_tools import search_airports, search_flights"
    },
    {
        "name": "hotel",
        "prompt_var": "HOTEL_AGENT_SYSTEM",
        "index": 4,
        "imports": "from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent, llm_fast",
        "tools": "from src.tools.dotnet_tools import search_hotels\nfrom src.tools.place_resolver import resolve_place"
    },
    {
        "name": "restaurant",
        "prompt_var": "RESTAURANT_AGENT_SYSTEM",
        "index": 5,
        "imports": "from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent, llm_fast",
        "tools": "from src.tools.maps_tools import places_nearby_search, places_text_search_id_only\nfrom src.tools.place_resolver import resolve_place"
    },
    {
        "name": "itinerary",
        "prompt_var": "ITINERARY_AGENT_SYSTEM",
        "index": 6,
        "imports": "from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent",
        "tools": "from src.tools.maps_tools import get_distance_matrix\nfrom src.tools.itinerary_tools import optimize_daily_itinerary"
    },
    {
        "name": "preparation",
        "prompt_var": "PREPARATION_AGENT_SYSTEM",
        "index": 7,
        "imports": "from src.agents.nodes.utils import _extract_json, _run_agent_with_tools, llm_agent",
        "tools": "from src.tools.dotnet_tools import get_weather_forecast\nfrom src.tools.search_tools import tavily_search"
    },
    {
        "name": "synthesize",
        "prompt_var": "SYNTHESIZE_SYSTEM",
        "index": 8,
        "imports": "from src.agents.nodes.utils import llm_streaming",
        "tools": ""
    }
]

for agent in agents:
    file_content = f"""import json
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.agents.state import GraphState
{agent['imports']}
{agent['tools']}

logger = logging.getLogger(__name__)

{prompts[agent['prompt_var']]}
{parts[agent['index']]}"""

    with open(os.path.join(nodes_dir, f"{agent['name']}.py"), "w", encoding="utf-8") as f:
        f.write(file_content)

# create __init__.py
init_content = """from src.agents.nodes.utils import _extract_json, _get_latest_user_message, _get_conversation_context, _run_agent_with_tools, llm_fast, llm_streaming, llm_agent
from src.agents.nodes.orchestrator import orchestrator_node
from src.agents.nodes.attraction import attraction_agent_node
from src.agents.nodes.flight import flight_agent_node
from src.agents.nodes.hotel import hotel_agent_node
from src.agents.nodes.restaurant import restaurant_agent_node
from src.agents.nodes.itinerary import itinerary_agent_node
from src.agents.nodes.preparation import preparation_agent_node
from src.agents.nodes.synthesize import synthesize_agent_node

__all__ = [
    "orchestrator_node",
    "attraction_agent_node",
    "flight_agent_node",
    "hotel_agent_node",
    "restaurant_agent_node",
    "itinerary_agent_node",
    "preparation_agent_node",
    "synthesize_agent_node",
]
"""
with open(os.path.join(nodes_dir, "__init__.py"), "w", encoding="utf-8") as f:
    f.write(init_content)

print("Split completed successfully.")
