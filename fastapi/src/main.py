"""
FastAPI Multi-Agent Application.

This is the main entry point for the FastAPI application that supports
LangGraph multi-agent workflows with WebSocket streaming and .NET API integration.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.api import api_router
from src.api.routes.websocket import router as ws_router
import logging
import os
import sys
import asyncio
from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

# Apply Windows event loop policy for Psycopg 3 compatibility if on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME}")
    logger.info(f"API running on {settings.HOST}:{settings.PORT}")
    logger.info(f".NET API URL: {settings.DOTNET_API_URL}")
    
    # Setup LangSmith tracing if configured
    if settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
        logger.info(f"LangSmith tracing enabled — project: {settings.LANGSMITH_PROJECT}")
    else:
        logger.info("LangSmith tracing disabled (set LANGSMITH_TRACING=true to enable)")
    
    # Initialize checkpointer and graph
    # Using the context manager keeps the connection pool alive for the app's lifetime
    try:
        from src.agents.graph import init_graph
        async with AsyncPostgresSaver.from_conn_string(settings.POSTGRES_URL) as checkpointer:
            # Create LangGraph internal tracking tables if they don't exist
            await checkpointer.setup()
            
            # Compile graph instances globally
            await init_graph(checkpointer=checkpointer)
            
            logger.info("LangGraph multi-agent workflow ready (PostgresSaver lifespan active)")
            logger.info("WebSocket endpoint: ws://localhost:8000/ws/agent/{conversation_id}")
            
            # Yield to FastAPI so it works
            yield
            
    except Exception as e:
        logger.error(f"❌ Failed to start LangGraph checkpointer (Postgres might be down or not created): {e}", exc_info=True)
        # Fallback to no checkpointer if Postgres fails (so dev can continue)
        logger.warning("⚠️ Falling back to NO CHECKPOINTER state. Agent states will NOT be persisted!")
        from src.agents.graph import init_graph
        await init_graph(checkpointer=None)
        yield
        
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="FastAPI backend with LangGraph multi-agent support and .NET integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS - Allow .NET API and React frontend to call this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React frontend
        "https://localhost:3000",  # React frontend (HTTPS)
        "http://localhost:5001",  # .NET API (HTTP)
        "https://localhost:5001",  # .NET API (HTTPS)
        settings.DOTNET_API_URL,  # Configured .NET URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)
app.include_router(ws_router)

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "FastAPI Multi-Agent System",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "websocket": "ws://localhost:8000/ws/agent/{conversation_id}"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
