"""
Agent Nodes for the LangGraph multi-agent workflow.

Uses real Google Gemini LLM for:
- planner_node: LLM-based routing (classify intent → research/details/greeting)
- researcher_node: Mock search data (no LLM needed for search)
- dotnet_integration_node: Mock .NET API call (no LLM needed)
- response_node: Real LLM streaming response generation

The LLM calls use langchain's ChatGoogleGenerativeAI so that
astream_events can capture on_chat_model_stream tokens for realtime streaming.
"""

import asyncio
import logging
from typing import Any
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.agents.state import GraphState
from src.services.dotnet_client import dotnet_client
from src.config import settings

logger = logging.getLogger(__name__)

# Initialize LLM — shared across nodes
# Using gemini-2.0-flash for fast responses and streaming
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=settings.GOOGLE_GEMINI_API_KEY,
    temperature=0.7,
    streaming=True,  # Enable streaming for on_chat_model_stream events
)

# System prompts for each agent
PLANNER_SYSTEM = """Bạn là Planner Agent cho hệ thống lập kế hoạch du lịch.
Nhiệm vụ: Phân tích tin nhắn của người dùng và phân loại thành MỘT trong các danh mục sau:

- "research" — nếu người dùng muốn tìm kiếm thông tin du lịch, điểm đến, tour, tham quan
- "details" — nếu người dùng yêu cầu thông tin chi tiết về giá cả, khách sạn, chuyến bay
- "greeting" — nếu chỉ là lời chào hỏi, câu hỏi đơn giản, hoặc trò chuyện thường

CHỈ ĐƯỢC trả lời ĐÚNG MỘT từ: research, details, hoặc greeting. Không giải thích gì thêm."""

RESPONSE_SYSTEM = """Bạn là Travel Planner AI Assistant — chuyên gia lập kế hoạch du lịch.
Trả lời bằng tiếng Việt, thân thiện và hữu ích.

{context}

Hãy trả lời câu hỏi của người dùng dựa trên thông tin hiện có. Nếu đây là lời chào, hãy giới thiệu bản thân ngắn gọn và hỏi người dùng muốn đi đâu.
Trả lời ngắn gọn, súc tích nhưng đầy đủ thông tin. Sử dụng emoji phù hợp."""


async def planner_node(state: GraphState) -> dict[str, Any]:
    """
    Orchestrator Agent — Uses LLM to classify intent and decide routing.
    
    The LLM classifies the user message into: research, details, or greeting.
    This determines which sub-agent to route to next.
    """
    logger.info("=" * 60)
    logger.info("🧠 [PLANNER] Node entered")

    messages = state.get("messages", [])
    latest_message = ""
    if messages:
        last_msg = messages[-1]
        latest_message = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    logger.info(f"   Latest message: {latest_message[:100]}")

    # Check if sub-agents already ran (loop back case)
    agent_outputs = state.get("agent_outputs", {})
    has_research = "researcher" in agent_outputs
    has_details = "dotnet_integration" in agent_outputs

    if has_research or has_details:
        logger.info("   📋 Sub-agent data collected, routing to RESPONSE")
        return {
            "current_agent": "planner",
            "current_tool": "",
            "plan_needs_research": False,
            "plan_needs_details": False,
            "agent_outputs": {
                **agent_outputs,
                "planner": {"plan_summary": "Sub-agent data collected, routing to response"}
            },
            "messages": [AIMessage(content="[Planner] Data collected, generating response...")],
        }

    # Use LLM to classify intent
    needs_research = False
    needs_details = False
    plan_summary = ""

    try:
        classify_messages = [
            SystemMessage(content=PLANNER_SYSTEM),
            HumanMessage(content=latest_message),
        ]
        # Use ainvoke (not streaming) for classification — just need the category
        result = await llm.ainvoke(classify_messages)
        # result = "greeting"  # Temporary hardcoded for testing without LLM
        category = result.content.strip().lower()
        logger.info(f"   LLM classification: '{category}'")

        if "research" in category:
            needs_research = True
            plan_summary = f"LLM classified as RESEARCH: '{latest_message[:50]}...'"
            logger.info("   🔍 Routing to RESEARCHER")
        elif "detail" in category:
            needs_details = True
            plan_summary = f"LLM classified as DETAILS: '{latest_message[:50]}...'"
            logger.info("   📡 Routing to DOTNET_INTEGRATION")
        else:
            plan_summary = f"LLM classified as GREETING: '{latest_message[:50]}...'"
            logger.info("   👋 Routing to RESPONSE (greeting)")

    except Exception as e:
        logger.error(f"   ❌ LLM classification failed: {e}")
        # Fallback: default to research for non-trivial messages
        if len(latest_message) > 20:
            needs_research = True
            plan_summary = f"Fallback routing to RESEARCH (LLM error)"
        else:
            plan_summary = f"Fallback routing to RESPONSE (LLM error)"

    logger.info(f"   Plan: {plan_summary}")
    logger.info("🧠 [PLANNER] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "planner",
        "current_tool": "",
        "plan_needs_research": needs_research,
        "plan_needs_details": needs_details,
        "agent_outputs": {
            **agent_outputs,
            "planner": {"plan_summary": plan_summary}
        },
        "messages": [AIMessage(content=f"[Planner] {plan_summary}")],
    }


async def researcher_node(state: GraphState) -> dict[str, Any]:
    """
    Researcher Agent — Searches for travel information.
    
    Currently uses mock data. In production, this would call search APIs
    (Google Places, TripAdvisor, etc.) to find real travel information.
    """
    logger.info("=" * 60)
    logger.info("🔍 [RESEARCHER] Node entered")

    # Simulate research delay (real API calls would take time)
    await asyncio.sleep(1.5)

    # Mock research results — these would come from real APIs later
    mock_attractions = [
        {"name": "Cầu Rồng (Dragon Bridge)", "type": "landmark", "rating": 4.5},
        {"name": "Bà Nà Hills", "type": "theme_park", "rating": 4.7},
        {"name": "Bãi biển Mỹ Khê", "type": "beach", "rating": 4.8},
        {"name": "Ngũ Hành Sơn (Marble Mountains)", "type": "nature", "rating": 4.6},
        {"name": "Chợ Hàn", "type": "market", "rating": 4.3},
    ]

    agent_outputs = state.get("agent_outputs", {})
    research_summary = f"Found {len(mock_attractions)} attractions"

    logger.info(f"   Results: {research_summary}")
    logger.info("🔍 [RESEARCHER] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "researcher",
        "current_tool": "search_attractions",
        "plan_needs_research": False,
        "agent_outputs": {
            **agent_outputs,
            "researcher": {
                "attractions": mock_attractions,
                "summary": research_summary,
            }
        },
        "messages": [AIMessage(content=f"[Researcher] {research_summary}")],
    }


async def dotnet_integration_node(state: GraphState) -> dict[str, Any]:
    """
    .NET Integration Agent — Calls the .NET backend API for detailed info.
    
    Attempts real .NET API call, falls back to mock data if unavailable.
    """
    logger.info("=" * 60)
    logger.info("📡 [DOTNET_INTEGRATION] Node entered")

    await asyncio.sleep(1.0)

    dotnet_response = {}
    try:
        logger.info("   Attempting .NET API call: GET /api/health")
        result = await dotnet_client.get("/api/health")
        dotnet_response = result
        logger.info(f"   .NET API response: {result.get('success', False)}")
    except Exception as e:
        logger.warning(f"   .NET API not available: {e}")
        dotnet_response = {
            "success": False, "mock": True,
            "data": {
                "place_details": {
                    "name": "Đà Nẵng", "country": "Vietnam",
                    "description": "Thành phố biển miền Trung Việt Nam",
                    "average_cost_per_day_usd": 50, "best_season": "February - May",
                },
                "hotels": [
                    {"name": "Hotel A", "price_per_night": 45, "rating": 4.2},
                    {"name": "Hotel B", "price_per_night": 80, "rating": 4.6},
                ],
            },
        }

    agent_outputs = state.get("agent_outputs", {})
    detail_summary = f"Fetched details: {'from .NET API' if dotnet_response.get('success') else 'mock data'}"

    logger.info(f"   {detail_summary}")
    logger.info("📡 [DOTNET_INTEGRATION] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "dotnet_integration",
        "current_tool": "dotnet_api_call",
        "plan_needs_details": False,
        "dotnet_api_response": dotnet_response,
        "agent_outputs": {
            **agent_outputs,
            "dotnet_integration": {
                "response": dotnet_response,
                "summary": detail_summary,
            }
        },
        "messages": [AIMessage(content=f"[DotNet Integration] {detail_summary}")],
    }


async def response_node(state: GraphState) -> dict[str, Any]:
    """
    Response Agent — Uses REAL LLM (Gemini) to generate the final response.
    
    This is where the actual text streaming happens.
    The LLM is called with ainvoke() inside this node, and astream_events
    at the graph level will automatically capture on_chat_model_stream tokens
    for realtime text streaming to the frontend.
    """
    logger.info("=" * 60)
    logger.info("📝 [RESPONSE] Node entered — Using REAL LLM")

    agent_outputs = state.get("agent_outputs", {})
    conversation_messages = state.get("messages", [])

    # Build context from sub-agent outputs
    context_parts = []
    researcher_data = agent_outputs.get("researcher", {})
    dotnet_data = agent_outputs.get("dotnet_integration", {})

    if researcher_data:
        attractions = researcher_data.get("attractions", [])
        if attractions:
            context_parts.append("Kết quả tìm kiếm điểm tham quan:")
            for a in attractions:
                context_parts.append(f"  - {a['name']} (loại: {a['type']}, đánh giá: {a['rating']})")

    if dotnet_data:
        api_resp = dotnet_data.get("response", {})
        place_info = api_resp.get("data", {}).get("place_details", {})
        if place_info:
            context_parts.append(f"\nThông tin chi tiết:")
            context_parts.append(f"  - Địa điểm: {place_info.get('name', 'N/A')}")
            context_parts.append(f"  - Mô tả: {place_info.get('description', 'N/A')}")
            context_parts.append(f"  - Chi phí TB/ngày: ${place_info.get('average_cost_per_day_usd', 'N/A')}")
            context_parts.append(f"  - Mùa du lịch tốt nhất: {place_info.get('best_season', 'N/A')}")

        hotels = api_resp.get("data", {}).get("hotels", [])
        if hotels:
            context_parts.append(f"\nKhách sạn gợi ý:")
            for h in hotels:
                context_parts.append(f"  - {h['name']}: ${h['price_per_night']}/đêm, rating {h['rating']}")

    context_str = "\n".join(context_parts) if context_parts else "Không có dữ liệu tìm kiếm bổ sung."
    system_prompt = RESPONSE_SYSTEM.format(context=context_str)

    # Build message list for LLM: system + recent conversation (last 10 messages)
    llm_messages = [SystemMessage(content=system_prompt)]
    
    # Add conversation history (skip internal agent messages like [Planner], [Researcher])
    for msg in conversation_messages[-10:]:
        content = msg.content if hasattr(msg, "content") else str(msg)
        if content.startswith("["):
            continue  # Skip internal agent trace messages
        if isinstance(msg, HumanMessage):
            llm_messages.append(msg)
        elif isinstance(msg, AIMessage):
            llm_messages.append(msg)

    # Ensure at least one user message
    if not any(isinstance(m, HumanMessage) for m in llm_messages):
        llm_messages.append(HumanMessage(content="Xin chào"))

    # Call LLM — astream_events will capture on_chat_model_stream tokens automatically
    try:
        logger.info(f"   Calling Gemini LLM with {len(llm_messages)} messages...")
        result = await llm.ainvoke(llm_messages)
        final_response = result.content
        logger.info(f"   LLM response: {len(final_response)} chars")
    except Exception as e:
        logger.error(f"   ❌ LLM call failed: {e}")
        final_response = f"Xin lỗi, đã xảy ra lỗi khi xử lý yêu cầu của bạn. Vui lòng thử lại. (Error: {str(e)[:100]})"

    logger.info("📝 [RESPONSE] Node completed")
    logger.info("=" * 60)

    return {
        "current_agent": "response",
        "current_tool": "",
        "final_response": final_response,
        "messages": [AIMessage(content=final_response)],
    }
