"""
Mock LLM Client - Grounded Resource Edition.
Exclusively uses local JSON files in app/resources/data/ as the source of truth.
No live APIs, no invented places.
"""
import re
import json
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

class MockLLMClient:
    """
    Grounded Mock LLM Client.
    Source of truth: app/resources/data/*.json
    """
    
    def __init__(self):
        self.model = "mock-resource-grounded"
        # Root of the data resources
        self.base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "data")
        self.rules = self._load_json("rules.json")
        self.destinations_map = self._load_json("destinations.json")
        self.user_agent = "TravelPlannerBot/1.0 (admin@example.com)"

    def _load_json(self, filename: str) -> Dict[str, Any]:
        """Utility to load a JSON resource file."""
        path = os.path.join(self.base_path, filename)
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            logger.warning(f"Resource not found: {path}")
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
        return {}

    def _get_city_resource(self, city_name: str) -> Optional[Dict[str, Any]]:
        """Load city-specific POI data."""
        clean_name = city_name.lower().replace(" ", "_").replace("-", "_")
        return self._load_json(f"{clean_name}.json")

    async def chat(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> str:
        """Process chat grounding it in resource data."""
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        
        # Check if this is a Q&A request (Helpful Travel Assistant)
        if "helpful travel assistant" in system_msg.lower():
            # Try to extract city from system_msg first
            city_prefix = "travel assistant for "
            explicit_city = None
            if city_prefix in system_msg.lower():
                # Extract city and remove any trailing punctuation
                city_part = system_msg.lower().split(city_prefix)[1].split(".")[0].strip()
                for entry in self.destinations_map.get("destinations", []):
                    for city in entry["cities"]:
                        if city.lower() == city_part:
                            explicit_city = city
                            break
                    if explicit_city: break
            
            return self._handle_qa_grounded(user_msg, explicit_city=explicit_city)
            
        # Check for itinerary generation or modification
        if "itinerary" in system_msg.lower() or "plan" in system_msg.lower():
            if "CURRENT ITINERARY" in user_msg or "MODIFICATION REQUEST" in user_msg:
                # Modifying is just regenerating for this grounded demo
                return self._generate_grounded_itinerary(user_msg)
            return self._generate_grounded_itinerary(user_msg)
        
        return "I am grounded in backend data. Please ask about itineraries for supported cities."

    async def chat_json(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> dict:
        """Return parsed JSON response."""
        response = await self.chat(messages, temperature, max_tokens, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {"summary": "Error generating grounded JSON.", "days": []}

    def _generate_grounded_itinerary(self, prompt: str) -> str:
        """Generate itinerary using ONLY grounded JSON files."""
        # 1. Extract Info (Grounded Destinations)
        info = self._extract_travel_info(prompt)
        
        # Identify Grounded City
        city_match = None
        extracted_dests = info.get("destinations", [])
        if extracted_dests:
            target = extracted_dests[0].lower()
            for entry in self.destinations_map.get("destinations", []):
                if any(city.lower() == target for city in entry["cities"]):
                    # Match found in grounded list
                    city_match = target.title()
                    break
        
        if not city_match:
            return json.dumps({
                "summary": "Unsupported destination. I only have verified data for major global cities like Paris, London, Tokyo, NYC, Dubai, Delhi, Mumbai, Goa, and Ujjain.",
                "days": [],
                "error": "Dest not in dataset"
            })

        # 2. Load Resource
        city_res = self._get_city_resource(city_match)
        if not city_res:
            return json.dumps({"summary": f"Data file for {city_match} is missing.", "days": []})

        # 3. Apply Rules
        days = info.get("trip_duration_days", 3)
        pace = info.get("sightseeing_pace", "moderate")
        
        rules = self.rules.get("itinerary_constraints", {})
        pace_rule = rules.get("pace_definitions", {}).get(pace, rules.get("pace_definitions", {}).get("moderate"))
        max_acts = pace_rule.get("max_activities_per_day", 4)
        
        # 4. Generate Days
        poi_pool = []
        for cat, items in city_res.get("categories", {}).items():
            for item in items:
                poi_pool.append({"name": item["name"], "type": cat, "desc": item["description"]})
        
        import random
        random.seed(city_match + str(days)) # Deterministic for city/duration
        
        itinerary_days = []
        start_date = datetime.now()
        
        for d in range(1, days + 1):
            # Select unique POIs for this day if possible
            sample_size = min(max_acts, len(poi_pool))
            day_pois = random.sample(poi_pool, sample_size)
            
            activities = []
            curr_time = datetime.strptime("09:00", "%H:%M")
            
            for poi in day_pois:
                duration = pace_rule.get("min_duration_minutes", 60)
                end_time = curr_time + timedelta(minutes=duration)
                activities.append({
                    "time_slot": f"{curr_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}",
                    "location": poi["name"],
                    "activity_type": poi["type"],
                    "description": poi["desc"],
                    "duration_minutes": duration,
                    "travel_distance_km": 5.0
                })
                curr_time = end_time + timedelta(minutes=pace_rule.get("gap_between_activities_minutes", 30))
            
            itinerary_days.append({
                "day_number": d,
                "date": (start_date + timedelta(days=d-1)).strftime("%Y-%m-%d"),
                "theme": f"Exploring {city_match} Highlights",
                "activities": activities,
                "total_distance_km": len(activities) * 5.0
            })

        return json.dumps({
            "summary": f"A grounded {days}-day itinerary for {city_match} using only verified data.",
            "days": itinerary_days,
            "suggestions": [{"name": p["name"], "type": p["type"]} for p in random.sample(poi_pool, min(3, len(poi_pool)))],
            "pro_tips": ["Follow local customs and dress modestly at religious sites.", "Use public transport for efficiency."],
            "grounding_source": "Local JSON Dataset"
        })

    def _handle_qa_grounded(self, prompt: str, explicit_city: str = None) -> str:
        """Ground QA answers in city resources."""
        prompt_lower = prompt.lower()
        city_match = None
        
        # 1. Try searching in the question part first (Highest priority: User's intent)
        if "itinerary context:" in prompt_lower:
            question_part = prompt_lower.split("itinerary context:")[0]
        elif "itinerary context:" in prompt_lower.lower():
             # Handle any casing
             idx = prompt_lower.lower().find("itinerary context:")
             question_part = prompt_lower[:idx]
        else:
            question_part = prompt_lower
        for entry in self.destinations_map.get("destinations", []):
            for city in entry["cities"]:
                if city.lower() in question_part:
                    city_match = city
                    break
            if city_match: break
        
        # 2. Use explicit city from system message (Session intent)
        if not city_match and explicit_city:
            city_match = explicit_city
        
        # 3. Final fallback: search entire prompt (Contextual match)
        if not city_match:
            for entry in self.destinations_map.get("destinations", []):
                for city in entry["cities"]:
                    if city.lower() in prompt_lower:
                        city_match = city
                        break
                if city_match: break
            
        if not city_match:
            return "I can answer questions about Paris, London, Tokyo, NYC, Dubai, Delhi, Mumbai, Goa, and Ujjain. Which are you visiting?"
            
        city_res = self._get_city_resource(city_match)
        if not city_res: return f"I have {city_match} in my registry but no detail data yet."

        if re.search(r"food|eat|restaurant|dining", question_part, re.IGNORECASE):
            poi = city_res.get("categories", {}).get("food", [])
            return f"In {city_match}, verified food spots include: " + ", ".join([f['name'] for f in poi[:3]])
            
        if re.search(r"market|shopping|bazaar|mall", question_part, re.IGNORECASE):
            poi = city_res.get("categories", {}).get("markets", [])
            return f"Verified markets in {city_match}: " + ", ".join([m['name'] for m in poi[:3]])

        return f"I have verified data for {city_match} covering heritage, food, markets, and nature. What do you need?"

    def _extract_travel_info(self, text: str) -> dict:
        """Helper to extract travel parameters from text."""
        text_lower = text.lower()
        res = {}
        
        # Match cities from destinations.json
        cities = []
        for entry in self.destinations_map.get("destinations", []):
            for city in entry["cities"]:
                if city.lower() in text_lower:
                    cities.append(city)
        if cities: res["destinations"] = cities
        
        # Duration
        d_match = re.search(r"(?:trip duration|duration)[\s:]+(\d+)", text_lower)
        if not d_match:
            d_match = re.search(r"(\d+)\s*days?", text_lower)
        if d_match: res["trip_duration_days"] = int(d_match.group(1))
        
        # Pace
        if "relaxed" in text_lower: res["sightseeing_pace"] = "relaxed"
        elif "packed" in text_lower: res["sightseeing_pace"] = "packed"
        else: res["sightseeing_pace"] = "moderate"
            
        return res
