"""
LLM Client - Unified interface for multiple LLM providers.
Supports OpenAI, Mistral, OpenRouter, and Ollama.
"""
from openai import AsyncOpenAI
from typing import Optional
import json
import re

from ..config import get_llm_config


class LLMClient:
    """Async LLM client with OpenAI-compatible API."""
    
    def __init__(self):
        from ..config import settings
        config = get_llm_config()
        
        # Use mock client if provider is 'mock'
        if settings.llm_provider == "mock":
            from .mock_llm import MockLLMClient
            self._mock = MockLLMClient()
            self.model = "mock-demo"
            self.temperature = 0.7
            self.max_tokens = 2000
            self.client = None
        elif settings.llm_provider == "local":
            from .local_llm import LocalLLMClient
            import logging
            logger = logging.getLogger(__name__)
            try:
                self._mock = LocalLLMClient()
                self.model = self._mock.model_name
            except Exception as e:
                logger.error(f"Local LLM init failed, falling back to Mock: {e}")
                from .mock_llm import MockLLMClient
                self._mock = MockLLMClient()
                self.model = "mock-fallback"
            
            self.temperature = 0.7
            self.max_tokens = 512
            self.client = None
        else:
            self._mock = None
            self.client = AsyncOpenAI(
                api_key=config["api_key"],
                base_url=config["base_url"]
            )
            self.model = config["model"]
            self.temperature = config["temperature"]
            self.max_tokens = config["max_tokens"]
    
    async def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> str:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens
            json_mode: If True, request JSON response format
            
        Returns:
            The assistant's response content
        """
        # Use mock client if available
        if self._mock is not None:
            return await self._mock.chat(messages, temperature, max_tokens, json_mode)
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        
        # JSON mode support (not all providers support this)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        
        try:
            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            # If JSON mode fails, retry without it
            if json_mode and "response_format" in kwargs:
                del kwargs["response_format"]
                response = await self.client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            raise e
    
    async def chat_json(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> dict:
        """
        Send a chat request and parse JSON response.
        
        Returns:
            Parsed JSON dict
        """
        response = await self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True
        )
        
        # Extract JSON from response
        return self._parse_json_response(response)
    
    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from LLM response, handling markdown code blocks."""
        text = text.strip()
        
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try extracting from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        
        # Try finding JSON object in text
        brace_start = text.find('{')
        brace_end = text.rfind('}')
        if brace_start != -1 and brace_end > brace_start:
            try:
                return json.loads(text[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass
        
        # Return empty dict if parsing fails
        return {}


# Global LLM client instance
llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client."""
    global llm_client
    if llm_client is None:
        llm_client = LLMClient()
    return llm_client
