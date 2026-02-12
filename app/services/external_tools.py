"""
External Tools Service.
Handles interactions with OpenStreetMap, Foursquare, and OpenRouteService.
"""
import httpx
import asyncio
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
        Update travel distances in the itinerary using Local DB coordinates and Haversine formula.
        """
        from math import radians, cos, sin, asin, sqrt
        from .local_database import local_db

        def haversine(lon1, lat1, lon2, lat2):
            """
            Calculate the great circle distance in kilometers between two points 
            on the earth (specified in decimal degrees)
            """
            # convert decimal degrees to radians 
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

            # haversine formula 
            dlon = lon2 - lon1 
            dlat = lat2 - lat1 
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a)) 
            r = 6371 # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
            return c * r

        # 1. Get City Center Coordinates (as starting point for first day)
        # We assume the main destination is available or we pick the first activty
        
        for day in itinerary.get("days", []):
            # Ensure total_distance_km exists
            if "total_distance_km" not in day:
                day["total_distance_km"] = 0.0
                
            activities = day.get("activities", [])
            if not activities:
                continue
                
            # Previous location coordinates (start empty)
            prev_coords = None
            
            # If we have a city in the itinerary summary or context, we could look it up.
            # For now, let's assume the first activity starts from "somewhere" (maybe hotel).
            # If the user provides a "Hotel" in hotel_recommendations, we could use that as start?
            # Complexity: effectively we just want distance between sequential activities.
            
            for i, activity in enumerate(activities):
                location_name = activity.get("location")
                current_coords = None
                
                # Check Local DB
                local_coords = local_db.get_coordinates(location_name)
                
                if local_coords:
                    current_coords = local_coords
                else:
                    # Fallback to OSM (cached/live)
                    # For performance, maybe skip live OSM for now or use the get_coordinates method
                    # which uses OSM.
                    current_coords = await self.get_coordinates(location_name)
                
                if prev_coords and current_coords:
                    dist = haversine(prev_coords[0], prev_coords[1], current_coords[0], current_coords[1])
                    activity["travel_distance_km"] = round(dist, 2)
                    day["total_distance_km"] += round(dist, 2)
                else:
                     # First activity or missing coords
                     activity["travel_distance_km"] = 0.0 # Or keep what LLM guessed if we trust it?
                     # Let's keep LLM guess if we fail to calc
                     if activity.get("travel_distance_km") == 0:
                         pass
                
                if current_coords:
                    prev_coords = current_coords
                    
        return itinerary


    async def get_recommendations(self, destination: str, budget: str = "standard", start_date: str = None, end_date: str = None) -> str:
        """
        Fetch real-world hotels, restaurants, and weather forecast from Local DB and External APIs.
        """
        # 0. Fetch Weather if dates available
        weather_info = "Weather data not requested."
        if start_date and end_date:
            coords = await self.get_coordinates(destination)
            if coords:
                weather_info = await self.get_weather_forecast(coords[1], coords[0], start_date, end_date)
        
        context = f"REAL-WORLD DATA FOR {destination.upper()} ({budget.upper()} BUDGET):\n\n"
        context += f"LOCAL WEATHER FORECAST:\n{weather_info}\n\n"

        # 1. Check Local Database FIRST
        from .local_database import local_db
        local_data_found = False
        
        try:
            city_status = local_db.get_city_status(destination)
            if city_status['found']:
                official_name = city_status['official_name']
                logger.info(f"Local data found for {official_name}")
                
                # Fetch Local Data
                local_hotels = local_db.get_hotels(official_name)
                local_food = local_db.get_restaurants(official_name)
                local_areas = local_db.get_areas(official_name)
                
                if local_hotels or local_food or local_areas:
                    local_data_found = True
                    context += "=== VERIFIED LOCAL DATABASE DATA ===\n"
                    
                    if local_areas:
                        context += "MAJOR AREAS & ATTRACTIONS:\n"
                        for area in local_areas:
                            context += f"- {area['name']} ({area['type']}) - Tags: {area['tags']}\n"
                        context += "\n"
                        
                    if local_hotels:
                        context += "VERIFIED HOTELS:\n"
                        # Simple budget filtering logic or return top 5
                        for h in local_hotels[:8]: 
                            context += f"- {h['name']} ({h['category']}) - Location: {h['lat']}, {h['lon']}\n"
                        context += "\n"
                        
                    if local_food:
                        context += "VERIFIED RESTAURANTS:\n"
                        for r in local_food[:8]:
                            context += f"- {r['name']} ({r['cuisine']} - {r['category']})\n"
                        context += "\n"
        except Exception as e:
            logger.error(f"Local DB Error: {e}")

        # 2. Fetch External Data if needed (or to augment)
        # We ALWAYS fetch external data for now to ensure richness, especially given the DB might be limited
        # But we mark it clearly
        
        # Map budget to search terms
        budget_map = {
            "economy": {"hotel": "budget hostel", "food": "best street food"},
            "standard": {"hotel": "mid-range hotel", "food": "top rated restaurants"},
            "luxury": {"hotel": "4-star hotels", "food": "fine dining restaurants"},
            "lavish": {"hotel": "luxury 5-star hotels", "food": "Michelin star restaurants"}
        }
        terms = budget_map.get(budget.lower(), budget_map["standard"])
        
        # Sequential searches for a holistic city profile
        # Track specifically for malls/modern spots vs cultural/historic
        top_spots = await self.get_osm_places(f"famous landmarks and top sights in {destination}", limit=10)
        await asyncio.sleep(1.1)
        
        # Only fetch these if local data was sparse or missing
        if not local_data_found or len(local_areas if 'local_areas' in locals() else []) < 3:
             malls = await self.get_osm_places(f"large shopping malls and commercial centers in {destination}", limit=8)
             await asyncio.sleep(1.1)
             culture = await self.get_osm_places(f"famous temples and historical museums in {destination}", limit=10)
             all_pois = top_spots + culture + malls
        else:
            all_pois = top_spots # Just get top spots to augment local areas

        
        await asyncio.sleep(1.1)
        hotels = await self.get_osm_places(f"{terms['hotel']} in {destination}", limit=5)
        await asyncio.sleep(1.1)
        restaurants = await self.get_osm_places(f"{terms['food']} or top rated dining in {destination}", limit=5)
        
        context += "=== SUPPLEMENTARY WEB DATA ===\n"
        
        if all_pois:
            context += "ADDITIONAL LANDMARKS:\n"
            seen = set()
            count = 0
            for p in all_pois:
                name = p.get('display_name').split(',')[0]
                if name not in seen and count < 15:
                    context += f"- {name} (Category: {p.get('type')})\n"
                    seen.add(name)
                    count += 1
        
        if hotels and not local_data_found: # Prefer local hotels if available
            context += "\nADDITIONAL HOTELS:\n"
            for h in hotels[:3]:
                name = h.get('display_name').split(',')[0]
                context += f"- {name} (Matches {budget} budget)\n"
                
        if restaurants and not local_data_found: # Prefer local restaurants
            context += "\nADDITIONAL RESTAURANTS:\n"
            for r in restaurants[:4]:
                name = r.get('display_name').split(',')[0]
                context += f"- {name} (Cuisine: {r.get('type')})\n"
                
        return context

# Global instance
external_tools = ExternalToolsService()
