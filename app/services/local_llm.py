import logging
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from app.services.mock_llm import MockLLMClient
import json

logger = logging.getLogger(__name__)

class LocalLLMClient(MockLLMClient):
    """
    Local LLM Client using atharvpareta07/travel-planner-mistral-7b.
    Inherits structured generation logic from MockLLMClient but replaces
    'creative' parts with actual LLM generation.
    """
    
    def __init__(self):
        super().__init__()
        self.model_name = "atharvpareta07/travel-planner-mistral-7b"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Initializing LocalLLMClient with {self.model_name} on {self.device}...")
        
        try:
            # Try AutoTokenizer first, fallback to LlamaTokenizer (for Mistral/Llama finetunes)
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            except Exception:
                from transformers import LlamaTokenizer
                logger.warning("AutoTokenizer failed, falling back to LlamaTokenizer")
                self.tokenizer = LlamaTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
                
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                device_map="auto",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                low_cpu_mem_usage=True
            )
            
            self.pipe = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                max_new_tokens=512,
                do_sample=True,
                temperature=0.7,
                top_p=0.95,
                repetition_penalty=1.15
            )
            logger.info("Local LLM loaded successfully.")
            
        except Exception as e:
            logger.error(f"Failed to load Local LLM: {e}")
            raise e

    async def chat(self, messages: list[dict], temperature: float = 0.7, max_tokens: int = 512, json_mode: bool = False) -> str:
        """
        Generate response using local Mistral model.
        """
        # 1. Check for utility requests (extraction/itinerary gen)
        # We perform the same checks as Mock to preserve the robust logic
        # but for 'general chat', we use the model.
        
        system_msg = ""
        user_msg = ""
        for msg in messages:
            if msg["role"] == "user":
                user_msg = msg["content"]
            elif msg["role"] == "system":
                system_msg = msg["content"]
        
        # Pass extract/plan requests to the deterministic logic (inherited)
        # This keeps the "Smart Faking" and "Live Data" logic active for form submission.
        if "travel information extractor" in system_msg.lower():
            return json.dumps(self._extract_travel_info(user_msg))
            
        if "itinerary" in system_msg.lower() or "plan" in system_msg.lower():
             if "CURRENT ITINERARY" in user_msg or "MODIFICATION REQUEST" in user_msg:
                return self._modify_itinerary(user_msg)
             # Note: _generate_grounded_itinerary uses Verified JSON Resources
             return self._generate_grounded_itinerary(user_msg)

        # 2. For general chat/Q&A, use the LLM
        logger.info("Generating Local LLM response...")
        
        # Format prompt for Mistral [INST] ... [/INST]
        # Simplistic formatting
        prompt = f"[INST] {system_msg}\n\n{user_msg} [/INST]"
        
        try:
            output = self.pipe(prompt)
            generated_text = output[0]['generated_text']
            # Remove the prompt from the output
            response = generated_text.replace(prompt, "").strip()
            return response
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return "I apologize, but I encountered an error generating a response."

    def _generate_pro_tips(self, destination: str, known_key: str) -> list[str]:
        """
        Override: Use LLM to generate real tips for the destination.
        """
        # Fetch live context first
        summary, entities = self._fetch_live_city_data(destination)
        
        context = f"City: {destination}.\nSummary: {summary[:500] if summary else 'A beautiful destination.'}"
        
        prompt = f"""[INST] You are a travel expert. Generate 3 short, practical, and specific pro-tips for a traveler visiting {destination}. 
        Focus on local etiquette, safety, or hidden gems.
        Context: {context}
        Format: Return ONLY a JSON list of strings, e.g., ["Tip 1", "Tip 2", "Tip 3"]. [/INST]"""
        
        try:
            output = self.pipe(prompt, max_new_tokens=200)
            text = output[0]['generated_text'].replace(prompt, "").strip()
            
            # Simple cleanup to find list
            start = text.find('[')
            end = text.rfind(']')
            if start != -1 and end != -1:
                json_str = text[start:end+1]
                return json.loads(json_str)
            else:
                # Fallback parsing
                lines = [l.strip('- ').strip() for l in text.split('\n') if l.strip()]
                return lines[:3]
                
        except Exception as e:
            logger.warning(f"LLM Tip generation failed: {e}")
            # Fallback to Mock logic
            return super()._generate_pro_tips(destination, known_key)
