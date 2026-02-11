"""
External Tools Service.
Handles interactions with OpenStreetMap, Foursquare, and OpenRouteService.
"""
import httpx
from typing import List, Dict, Optional
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class ExternalToolsService:
    """Service to interact with external APIs."""
    
    def __init__(self):
        self.foursquare_key = settings.foursquare_api_key
        self.ors_key = settings.ors_api_key
        self.headers_fs = {
            "Authorization": self.foursquare_key,
            "Accept": "application/json"
        }
        self.headers_ors = {
            "Authorization": self.ors_key,
            "Accept": "application/json"
        }

    async def get_osm_places(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search for places using OpenStreetMap (Nominatim).
        """
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": limit
        }
        # Nominatim requires a user-agent
        headers = {"User-Agent": "TravelPlannerApp/1.0"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"OSM Error: {e}")
                return []

    async def get_foursquare_food(self, near: str, query: str = "food", limit: int = 5) -> List[Dict]:
        """
        Search for food/venues using Foursquare.
        """
        if not self.foursquare_key:
            logger.warning("No Foursquare API key provided.")
            return []
            
        url = "https://api.foursquare.com/v3/places/search"
        params = {
            "near": near,
            "query": query,
            "limit": limit,
            "sort": "RATING"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers_fs, params=params)
                response.raise_for_status()
                data = response.json()
                results = []
                for place in data.get("results", []):
                    results.append({
                        "name": place.get("name"),
                        "location": place.get("location", {}).get("formatted_address"),
                        "categories": [c["name"] for c in place.get("categories", [])],
                        "distance": place.get("distance")
                    })
                return results
            except Exception as e:
                logger.error(f"Foursquare Error: {e}")
                return []

    async def get_ors_distancematrix(self, locations: List[List[float]]) -> Dict:
        """
        Calculate distance matrix using OpenRouteService.
        locations: List of [lon, lat] coordinates.
        """
        if not self.ors_key:
            # logger.warning("No ORS API key provided.")
            return {}
            
        url = "https://api.openrouteservice.org/v2/matrix/driving-car"
        payload = {"locations": locations, "metrics": ["distance", "duration"]}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers_ors)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"ORS Error: {e}")
                return {}

    async def get_weather_forecast(self, lat: float, lon: float, start_date: str, end_date: str) -> str:
        """
        Fetch weather forecast from Open-Meteo (No API key required).
        """
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min",
            "timezone": "auto",
            "start_date": start_date,
            "end_date": end_date
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                daily = data.get("daily", {})
                dates = daily.get("time", [])
                max_temps = daily.get("temperature_2m_max", [])
                min_temps = daily.get("temperature_2m_min", [])
                codes = daily.get("weather_code", [])
                
                weather_summary = []
                for i in range(len(dates)):
                    code = codes[i]
                    # Simple weather code mapping
                    condition = "Clear"
                    if code > 0: condition = "Cloudy"
                    if code >= 51: condition = "Rainy"
                    if code >= 71: condition = "Snowy"
                    if code >= 95: condition = "Stormy"
                    
                    weather_summary.append(f"{dates[i]}: {condition} ({min_temps[i]}°C to {max_temps[i]}°C)")
                
                return "\n".join(weather_summary)
            except Exception as e:
                logger.error(f"Weather API Error: {e}")
                return "Weather data unavailable."

    async def get_coordinates(self, place_name: str) -> Optional[List[float]]:
        """
        Get [lon, lat] for a place name using OSM.
        """
        results = await self.get_osm_places(place_name, limit=1)
        if results:
            # OSM returns lat/lon as strings, and in lat, lon order.
            # ORS needs lon, lat.
            try:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                return [lon, lat]
            except (ValueError, KeyError):
                pass
        return None

    async def update_itinerary_distances(self, itinerary: Dict) -> Dict:
        """
        Update travel distances in the itinerary using ORS.
        This operates on the dictionary representation before parsing to objects, 
        or we can modify to work on objects.
        For simplicity, let's assume it takes the parsed Itinerary object or we call this *after* parsing.
        """
        # Note: This implementation is a placeholder for the complex logic of 
        # extracting all locations, batching ORS calls, and updating the structure.
        # For now, we will skip the heavy implementation to avoid rate limits and complexity 
        # in this turn, but providing the infrastructure.
        return itinerary


    async def get_recommendations(self, destination: str, budget: str = "standard", start_date: str = None, end_date: str = None) -> str:
        """
        Fetch real-world hotels, restaurants, and weather forecast.
        """
        # 0. Fetch Weather if dates available
        weather_info = "Weather data not requested."
        if start_date and end_date:
            coords = await self.get_coordinates(destination)
            if coords:
                weather_info = await self.get_weather_forecast(coords[1], coords[0], start_date, end_date)
        
        # 1. Map budget to search terms
        budget_map = {
            "economy": {"hotel": "budget hostel", "food": "best street food"},
            "standard": {"hotel": "mid-range hotel", "food": "top rated restaurants"},
            "luxury": {"hotel": "4-star hotels", "food": "fine dining restaurants"},
            "lavish": {"hotel": "luxury 5-star hotels", "food": "Michelin star restaurants"}
        }
        terms = budget_map.get(budget.lower(), budget_map["standard"])
        
        # 2. Sequential searches for a holistic city profile
        # Track specifically for malls/modern spots vs cultural/historic
        top_spots = await self.get_osm_places(f"famous landmarks and top sights in {destination}", limit=10)
        await asyncio.sleep(1.1)
        malls = await self.get_osm_places(f"large shopping malls and commercial centers in {destination}", limit=8)
        await asyncio.sleep(1.1)
        culture = await self.get_osm_places(f"famous temples and historical museums in {destination}", limit=10)
        await asyncio.sleep(1.1)
        hotels = await self.get_osm_places(f"{terms['hotel']} in {destination}", limit=8)
        await asyncio.sleep(1.1)
        restaurants = await self.get_osm_places(f"{terms['food']} or top rated dining in {destination}", limit=8)
        
        context = f"REAL-WORLD DATA FOR {destination.upper()} ({budget.upper()} BUDGET):\n\n"
        context += f"LOCAL WEATHER FORECAST:\n{weather_info}\n\n"
        
        # Combine spots for the AI
        all_pois = top_spots + culture + malls
        if all_pois:
            context += "MAJOR LANDMARKS, MALLS & CULTURAL SPOTS:\n"
            seen = set()
            count = 0
            for p in all_pois:
                name = p.get('display_name').split(',')[0]
                if name not in seen and count < 20:
                    context += f"- {name} (Category: {p.get('type')})\n"
                    seen.add(name)
                    count += 1
        
        if hotels:
            context += "\nREAL HOTELS TO SUGGEST:\n"
            for h in hotels[:3]:
                name = h.get('display_name').split(',')[0]
                context += f"- {name} (Matches {budget} budget)\n"
                
        if restaurants:
            context += "\nREAL RESTAURANTS/CAFES:\n"
            for r in restaurants[:4]:
                name = r.get('display_name').split(',')[0]
                context += f"- {name} (Cuisine: {r.get('type')})\n"
                
        return context

# Global instance
external_tools = ExternalToolsService()
