"""
Real LLM Client - Connects to OpenAI, Mistral, Ollama, or Hugging Face.
"""
from typing import Optional, List, Dict, Any
import json
import logging
from openai import AsyncOpenAI
import httpx
# Import Hugging Face Client
try:
    from huggingface_hub import AsyncInferenceClient
except ImportError:
    AsyncInferenceClient = None
import re
import ast

from ..config import settings

logger = logging.getLogger(__name__)

class RealLLMClient:
    """
    Client for interacting with real LLMs via OpenAI-compatible API or native HF Client.
    """
    
    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        # Use provided URL or defaults
        self.base_url = settings.llm_base_url
        
        # Set defaults if missing
        if not self.base_url:
            if self.provider == "ollama":
                 self.base_url = "http://localhost:11434/v1"
            # HF doesn't strictly need a base_url if using the native client with a model ID, 
            # but we can respect it if provided.
        
        logger.info(f"Initializing RealLLMClient with provider={self.provider}, model={self.model}")
        
        if self.provider == "huggingface":
            # For Hugging Face Router, we use OpenAI client with custom base_url
            # We don't use AsyncInferenceClient because it validates repo IDs strictly,
            # and HF Router uses custom IDs like 'openai/gpt-oss-20b:groq'
            pass
            
        # Initialize OpenAI Compatible Client (Ollama, Mistral, OpenAI, Hugging Face)
        self.client = AsyncOpenAI(
            api_key=self.api_key if self.api_key else "dummy_key",
            base_url=self.base_url if self.base_url else None
        )

    async def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> str:
        """
        Process chat using the configured LLM provider.
        """
        try:
            response_format = {"type": "json_object"} if json_mode else None
            
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
                
            if json_mode and self.provider != "huggingface":
                kwargs["response_format"] = response_format
                
            # Explicit timeout to prevent early disconnects on slow generations
            kwargs["timeout"] = 120.0

            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM Chat Error: {e}")
            print(f"ERROR: LLM Chat Failed: {e}")
            # Fallback to a valid itinerary structure to inform the user
            # We assume this error might be a connection issue
            if "native client" in str(e).lower() or "connection" in str(e).lower() or "404" in str(e) or "401" in str(e):
                 # Only fallback if it looks like a connection/auth error
                 pass
            
            # Return a JSON-safe error string if simply chatting, or let chat_json handle the fallback if parsing fails.
            # But since chat() returns str, we return the error string.
            return f"Error communicating with AI: {str(e)}"
    
    async def chat_json(
        self,
        messages: list[dict],
        temperature: Optional[float] = 0.7,
        max_tokens: Optional[int] = None
    ) -> dict:
        """
        Process JSON request using the real LLM.
        """
        # Ensure system prompt asks for JSON
        if not any("json" in m.get("content", "").lower() for m in messages if m["role"] == "system"):
            messages[0]["content"] += "\n\nIMPORTANT: Return ONLY valid JSON."
            
        response_text = await self.chat(messages, temperature, max_tokens, json_mode=True)
        
        try:
            return self._repair_json(response_text)


        except Exception as e:
            logger.error(f"LLM Chat Error: {e}")
            print(f"ERROR: LLM Chat Failed: {e}")
            
            # Debug Log to file
            try:
                from datetime import datetime
                import traceback
                with open("llm_debug_error.log", "a") as f:
                    f.write(f"\n\n--- ERROR {datetime.now()} ---\n")
                    f.write(f"Exception: {str(e)}\n")
                    f.write(traceback.format_exc())
            except Exception as log_err:
                print(f"Failed to write log: {log_err}")

            # Fallback to a valid itinerary structure to inform the user
            return {
                "error": True,
                "summary": f"⚠️ AI Engine Unavailable ({self.provider}). please check configuration.",
                "days": [
                    {
                        "day_number": 1,
                        "date": "2024-01-01",
                        "theme": "System Check Required",
                        "activities": [
                            {
                                "time_slot": "Now",
                                "location": "Local Server",
                                "activity_type": "rest",
                                "description": f"Could not connect to AI Engine: {str(e)}",
                                "duration_minutes": 0,
                                "travel_distance_km": 0
                            }
                        ],
                        "total_distance_km": 0
                    }
                ]
            }

    def _repair_json(self, text: str) -> dict:
        """
        Attempt to clean and parse JSON that might be malformed or wrapped in text.
        """
        # Pre-cleaning: Normalize unicode characters using regex
        # Replace smart quotes (double)
        text = re.sub(r'[\u201c\u201d]', '"', text)
        # Replace smart quotes (single)
        text = re.sub(r"[\u2018\u2019]", "'", text)
        # Replace all dash variants (hyphen, non-breaking, en-dash, em-dash, etc.)
        text = re.sub(r'[\u2010-\u2015]', '-', text)
        
        try:
            # 1. Try direct parse
            return json.loads(text)
        except json.JSONDecodeError:
            print("DEBUG: JSON Direct Parse failed, trying cleanup...")
            pass

        cleaned_text = text.strip()

        # 2. Extract JSON from Markdown code blocks
        if "```" in cleaned_text:
            pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
            match = re.search(pattern, cleaned_text, re.DOTALL)
            if match:
                cleaned_text = match.group(1)
            else:
                # Fallback: remove simple fences
                cleaned_text = cleaned_text.replace("```json", "").replace("```", "").strip()
        
        # 3. Find first { and last }
        start = cleaned_text.find("{")
        end = cleaned_text.rfind("}")
        if start != -1 and end != -1:
            cleaned_text = cleaned_text[start:end+1]

        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            # 4. Try ast.literal_eval for Python-style dicts (single quotes)
            try:
                return ast.literal_eval(cleaned_text)
            except (ValueError, SyntaxError):
                pass
            
            # 5. Last resort: simple cleanup of common errors (trailing commas)
            # This is risky but helps with some LLMs
            try:
                # Remove trailing commas before matching brackets
                fixed_text = re.sub(r",\s*([\]}])", r"\1", cleaned_text)
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                # 6. Truncation Repair: If it looks truncated, try to close it
                try:
                    print("DEBUG: Attempting Truncation Repair...")
                    repaired = self._close_truncated_json(cleaned_text)
                    result = json.loads(repaired)
                    print("DEBUG: Truncation Repair SUCCESS!")
                    return result
                except Exception as e:
                    print(f"DEBUG: Truncation Repair failed: {e}")
                    pass

                # Include a snippet of the text in the error for debugging
                # Log full bad JSON to file for inspection
                with open("bad_json.log", "a") as f:
                    f.write(f"\n\n--- FAILED PARSE ATTEMPT ---\n")
                    f.write(f"RAW TEXT:\n{text}\n")
                    f.write(f"CLEANED TEXT:\n{cleaned_text}\n")
                raise Exception(f"Failed to parse JSON (length: {len(text)}). Check bad_json.log for details.")

    def _close_truncated_json(self, text: str) -> str:
        """
        Attempts to close truncated JSON by identifying unclosed brackets and braces.
        """
        # Step 1: Clean up any trailing partial content (heuristic)
        # Find the last "complete" structural boundary
        text = text.strip()
        
        # If it ends with something like '"key": "val', remove the ' "val' bit
        # This is a bit complex to do perfectly with regex, but we can try 
        # to find the last occurrence of something that looks like a completed field
        
        # Remove trailing partial words/quotes
        # e.g., '{"a": 1, "b": "hello' -> '{"a": 1'
        # We backtrack until we find a comma or a brace/bracket
        last_comma = text.rfind(',')
        last_brace = max(text.rfind('{'), text.rfind('['))
        
        # If we have a comma after the last brace, the last entry is definitely incomplete
        if last_comma > last_brace:
            text = text[:last_comma]
        
        # Now count brackets
        stack = []
        in_string = False
        escaped = False
        
        for char in text:
            if char == '"' and not escaped:
                in_string = not in_string
            elif char == '\\' and in_string:
                escaped = not escaped
                continue
            
            if not in_string:
                if char == '{': stack.append('}')
                elif char == '[': stack.append(']')
                elif char == '}': 
                    if stack and stack[-1] == '}': stack.pop()
                elif char == ']':
                    if stack and stack[-1] == ']': stack.pop()
            
            escaped = False
            
        if in_string:
            text += '"'
            
        # Add the closing characters in reverse order
        return text.strip() + ''.join(reversed(stack))
