"""
Configuration management for the travel planner.
Supports multiple LLM providers: OpenAI, Mistral, OpenRouter, Ollama.
"""
from pydantic_settings import BaseSettings
from typing import Literal
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Configuration
    llm_provider: str = "mock"
    llm_api_key: str = "mock"
    llm_model: str = "mock"
    llm_base_url: str = ""
    
    # Server Configuration
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True
    
    # External APIs (Optional/Unused for Grounded Engine)
    foursquare_api_key: str = ""
    ors_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()


def get_llm_config() -> dict:
    """Get LLM configuration from settings."""
    return {
        "provider": settings.llm_provider,
        "api_key": settings.llm_api_key,
        "model": settings.llm_model,
        "base_url": settings.llm_base_url
    }
