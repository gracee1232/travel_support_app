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
    # LLM Configuration
    llm_provider: Literal["openai", "mistral", "openrouter", "ollama", "mock", "local"] = "mock"
    llm_api_key: str = "ollama"  # Not needed for Ollama
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "mistral"
    
    # Server Configuration
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True
    
    # LLM Parameters
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_llm_config() -> dict:
    """Get LLM configuration based on provider."""
    config = {
        "api_key": settings.llm_api_key,
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }
    
    # Set base URL based on provider
    if settings.llm_provider == "ollama":
        config["base_url"] = settings.llm_base_url or "http://localhost:11434/v1"
    elif settings.llm_provider == "mistral":
        config["base_url"] = settings.llm_base_url or "https://api.mistral.ai/v1"
    elif settings.llm_provider == "openrouter":
        config["base_url"] = settings.llm_base_url or "https://openrouter.ai/api/v1"
    else:  # openai
        config["base_url"] = settings.llm_base_url or "https://api.openai.com/v1"
    
    return config
