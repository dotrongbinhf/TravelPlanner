"""
Configuration management for the FastAPI application.
Loads environment variables and provides type-safe configuration access.

If can not find in .env -> use default value
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # API Keys
    GOOGLE_GEMINI_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""
    XAI_API_KEY: str = ""
    USE_VERCEL_AI_GATEWAY: bool = False
    VERCEL_AI_GATEWAY_API_KEY: str = ""
    USE_ENTERPRISE_FIELDS: bool = False
    USE_ROUTE_MATRIX: bool = False

    GOOGLE_GEMINI_API_KEY_ORCHESTRATOR: str = ""
    GOOGLE_GEMINI_API_KEY_FLIGHT: str = ""
    GOOGLE_GEMINI_API_KEY_HOTEL: str = ""
    GOOGLE_GEMINI_API_KEY_ATTRACTION: str = ""
    GOOGLE_GEMINI_API_KEY_ITINERARY: str = ""
    GOOGLE_GEMINI_API_KEY_RESTAURANT: str = ""
    GOOGLE_GEMINI_API_KEY_PREPARATION: str = ""
    GOOGLE_GEMINI_API_KEY_SYNTHESIZE: str = ""
    
    # External services
    DOTNET_API_URL: str = "https://localhost:5001"
    
    # Application settings
    APP_NAME: str = "FastAPI Multi-Agent System"
    DEBUG: bool = True
    
    # LangSmith Tracing (optional)
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "travel-planner-multi-agents"
    LANGSMITH_TRACING: bool = False
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# Create a global settings instance
settings = Settings()
