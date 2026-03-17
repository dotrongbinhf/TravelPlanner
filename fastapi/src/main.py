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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="FastAPI backend with LangGraph multi-agent support and .NET integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
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
    
    # Log graph info
    from src.agents.graph import compiled_graph
    logger.info("LangGraph multi-agent workflow ready")
    logger.info("WebSocket endpoint: ws://localhost:8000/ws/agent/{conversation_id}")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info(f"Shutting down {settings.APP_NAME}")


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
