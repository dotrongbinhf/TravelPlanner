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
