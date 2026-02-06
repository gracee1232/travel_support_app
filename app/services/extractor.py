"""
Information Extractor - Role 1 AI.
Extracts travel planning facts from user messages.
"""
from typing import Optional
from datetime import datetime

from .llm_client import get_llm_client
from ..models.form_schema import TravelForm


EXTRACTOR_SYSTEM_PROMPT = """You are a travel information extractor. Your ONLY job is to extract travel planning facts from user messages and return them as JSON.

STRICT RULES:
1. Extract ONLY what the user explicitly states
2. Return null for any field not mentioned
3. Do NOT guess or infer missing values
4. Do NOT ask questions
5. Do NOT plan trips or give suggestions
6. Return ONLY valid JSON matching the exact field names below

FIELDS TO EXTRACT (use exact field names):
- trip_duration_days: integer (number of days)
- trip_duration_nights: integer (number of nights)
- traveler_count: integer (how many people)
- group_type: "solo" | "couple" | "family" | "group"
- destinations: array of strings (places to visit)
- start_date: "YYYY-MM-DD" format
- end_date: "YYYY-MM-DD" format
- daily_start_time: "HH:MM" format (when to start daily activities)
- daily_end_time: "HH:MM" format (when to end daily activities)
- weather_preference: "any" | "sunny" | "cloudy" | "mild"
- closed_days_restrictions: array of strings (days/dates to avoid)
- local_guidelines: string (any local rules mentioned)
- max_travel_distance_km: integer (max daily travel in km)
- sightseeing_pace: "relaxed" | "moderate" | "packed"
- cab_pickup_required: boolean
- hotel_checkin_time: "HH:MM" format
- hotel_checkout_time: "HH:MM" format
- traffic_consideration: boolean
- travel_mode: "driving" | "walking" | "public_transit" | "mixed"

ALSO EXTRACT:
- soft_preferences: array of strings (any preferences, wishes, or "I prefer..." statements that don't fit the above fields)

Respond with ONLY a JSON object. No explanations."""


class InformationExtractor:
    """Extracts structured travel information from user messages."""
    
    def __init__(self):
        self.llm = get_llm_client()
    
    async def extract(
        self,
        user_message: str,
        current_form: Optional[TravelForm] = None
    ) -> dict:
        """
        Extract travel information from a user message.
        
        Args:
            user_message: The user's chat message
            current_form: Current state of the form (for context)
            
        Returns:
            Dict with extracted fields (nulls for unmentioned fields)
            and soft_preferences list
        """
        # Build context with current form state
        context_parts = []
        if current_form:
            filled = current_form.get_filled_fields()
            if filled:
                context_parts.append(f"Already known: {filled}")
        
        # Add current date for relative date parsing
        context_parts.append(f"Today's date: {datetime.now().strftime('%Y-%m-%d')}")
        
        context = "\n".join(context_parts) if context_parts else "No prior context."
        
        messages = [
            {"role": "system", "content": EXTRACTOR_SYSTEM_PROMPT},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nUSER MESSAGE:\n{user_message}"}
        ]
        
        # Get extraction with low temperature for consistency
        result = await self.llm.chat_json(messages, temperature=0.1)
        
        # Clean and validate the result
        return self._clean_extraction(result)
    
    def _clean_extraction(self, data: dict) -> dict:
        """Clean and validate extracted data."""
        cleaned = {}
        
        # Handle each field type appropriately
        field_types = {
            "trip_duration_days": int,
            "trip_duration_nights": int,
            "traveler_count": int,
            "max_travel_distance_km": int,
            "group_type": str,
            "sightseeing_pace": str,
            "weather_preference": str,
            "travel_mode": str,
            "destinations": list,
            "closed_days_restrictions": list,
            "soft_preferences": list,
            "local_guidelines": str,
            "start_date": str,
            "end_date": str,
            "daily_start_time": str,
            "daily_end_time": str,
            "hotel_checkin_time": str,
            "hotel_checkout_time": str,
            "cab_pickup_required": bool,
            "traffic_consideration": bool,
        }
        
        for field, expected_type in field_types.items():
            value = data.get(field)
            
            if value is None or value == "" or value == []:
                continue
            
            try:
                if expected_type == int and not isinstance(value, int):
                    value = int(value)
                elif expected_type == bool and not isinstance(value, bool):
                    value = str(value).lower() in ("true", "yes", "1")
                elif expected_type == list and not isinstance(value, list):
                    value = [value] if value else []
                elif expected_type == str and not isinstance(value, str):
                    value = str(value)
                
                cleaned[field] = value
            except (ValueError, TypeError):
                # Skip invalid values
                continue
        
        return cleaned


# Global extractor instance
extractor: Optional[InformationExtractor] = None


def get_extractor() -> InformationExtractor:
    """Get or create the global extractor."""
    global extractor
    if extractor is None:
        extractor = InformationExtractor()
    return extractor
