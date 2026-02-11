"""
LLM Client - Unified interface for multiple LLM providers.
Supports OpenAI, Mistral, OpenRouter, and Ollama.
"""
from typing import Optional
import json
import re

from ..config import get_llm_config


class LLMClient:
    """
    Unified interface for the Grounded Engine (formerly Mock LLM).
    Removes all external LLM dependencies.
    """
    
    def __init__(self):
        llm_config = get_llm_config()
        self.provider = llm_config.get("provider", "mock")
        
        if self.provider == "mock":
            from .mock_llm import MockLLMClient
            self._engine = MockLLMClient()
            print("INFO: Using Grounded Mock Engine")
        else:
            from .real_llm import RealLLMClient
            self._engine = RealLLMClient()
            print(f"INFO: Using Real LLM Engine ({self.provider})")
    
    async def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> str:
        """
        Process chat using the grounded engine.
        """
        return await self._engine.chat(messages, temperature, max_tokens, json_mode)
    
    async def chat_json(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> dict:
        """
        Process JSON request using the grounded engine.
        """
        return await self._engine.chat_json(messages, temperature, max_tokens)


# Global LLM client instance
llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the global grounded engine client."""
    global llm_client
    if llm_client is None:
        llm_client = LLMClient()
    return llm_client
