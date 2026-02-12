"""
Itinerary Planner - Role 2 AI.
Generates day-wise travel itineraries based on constraints.
"""
import json
from typing import Optional
from datetime import datetime, timedelta

from .llm_client import get_llm_client
from ..models.form_schema import TravelForm
from ..models.itinerary import Itinerary, DayPlan, Activity, ActivityType
from .external_tools import external_tools



import traceback

PLANNER_SYSTEM_PROMPT = """You are a PROFESSIONAL TRAVEL PLANNING ENGINE integrated into a CRM platform.
Your job: generate highly polished, structured, premium-quality travel itineraries comparable to Itinr, MakeMyTrip, and Booking.com.
You are NOT a chatbot. You are a logistics planner + travel consultant + scheduler. Output must feel like a real, paid travel plan.

## STRICT RULES
- NEVER use emojis, icons, symbols, or casual language
- TIME FORMAT: '09:00 AM' or '01:30 PM' only. NEVER seconds
- Output must be clean, CRM-ready, professional

## PLANNING CONSTRAINT ENGINE (ALL MANDATORY)
1. Day density -- do NOT overload
2. Travel distance between locations
3. Traffic probability
4. Time required per attraction: Major landmark=1.5-2hrs, Museum=1-1.5hrs, Market=45-60min, Viewpoint=30-40min
5. Weather comfort (Hot: outdoor AM/PM, indoor midday | Rain: museums/cafes/covered | Cold: late start, indoor clusters)
6. Crowd patterns and peak timing
7. Hotel start/end logic (check-in/checkout timing respected)
8. Cab pickup timing and travel mode (cab/walk/metro/mix)
9. Closed day assumptions
10. Rest gaps between activities

## DENSITY CONTROL (PER DAY)
- 2 major attractions
- 1 secondary attraction
- 1 indoor activity (buffer)
- 1 lunch window
- 1 evening experience
- 1 dinner zone
Never overload. Never exceed this.

## AREA-CLUSTERING (CRITICAL)
Plan each day by geography. Example for Mumbai:
Day 1 = South Mumbai cluster, Day 2 = Fort + Marine Drive cluster, Day 3 = Bandra + Juhu cluster.
Avoid cross-city movement within a day.

## TIME STRUCTURE (STRICT)
09:00 AM - Start from hotel
10:30 AM - Major attraction
12:30 PM - Secondary place
01:30 PM - Lunch break
03:30 PM - Indoor/cultural spot
05:30 PM - Scenic walk
07:30 PM - Dinner area
09:00 PM - Return to hotel
Always include travel buffer and realistic pacing.

## HOTEL LOGIC
Hotel appears only at morning start and night return. Respect check-in/checkout times.
Check-in day = lighter morning. Checkout day = flexible exit.

## RESTAURANT RULE
Food is supportive, not dominant. Only include:
- 1 lunch area suggestion per day
- 1 dinner area suggestion per day
No food hopping.

## ANTI-HALLUCINATION
Use ONLY: dataset POIs, known landmarks, or recognized areas.
If specific data missing: use area-level planning, NOT fake names.

## QUALITY FILTER (PRE-OUTPUT CHECK)
Before outputting, verify: no repeated locations, no fake places, clean timeline, logical travel flow, balanced density, weather-adapted, distance-aware grouping.

## TONE
Professional. Structured. Calm. Concise. Confident. Like a real travel consultant report.

## OUTPUT SCHEMA (STRICT JSON)
Return strictly valid JSON:
{
  "summary": "Professional trip overview: destination, duration, travel type, weather overview, best areas to stay",
  "hotel_recommendations": [
    {
      "name": "Hotel Name",
      "rating": "Budget/Mid-Range/Luxury",
      "location": "Area name",
      "description": "Why suitable, professional summary",
      "price_range": "$$"
    }
  ],
  "days": [
    {
      "day_number": 1,
      "date": "YYYY-MM-DD",
      "theme": "Area Focus Title (e.g. South Mumbai Heritage Trail)",
      "weather": "Short weather summary for the day",
      "activities": [
        {
          "time": "09:00 AM",
          "location": "Place Name",
          "type": "sightseeing/meal/cultural/shopping/nature/travel/checkin/checkout",
          "description": "Professional description including travel mode and distance note",
          "duration_minutes": 120
        }
      ]
    }
  ]
}
"""

# ITINERARY GENERATION AND MODIFICATION LOGIC
# This section handles the generation of structured itineraries 
# using the elite travel concierge persona.



class ItineraryPlanner:
    """Generates travel itineraries based on constraints."""
    
    def __init__(self):
        self.llm = get_llm_client()
    
    async def generate(
        self,
        form: TravelForm,
        soft_preferences: list[str] = None
    ) -> Itinerary:
        """
        Generate a new itinerary based on form constraints.
        
        Args:
            form: The completed travel form (hard constraints)
            soft_preferences: Optional user preferences
            
        Returns:
            Generated Itinerary object
        """
        # Format constraints for the prompt
        constraints = self._format_constraints(form)
        preferences = "\n".join(soft_preferences) if soft_preferences else "None provided"
        
        # Fetch external context (Places & Food)
        try:
            destinations = form.destinations
            # Handle list, string, or None
            if isinstance(destinations, list) and destinations:
                main_dest = str(destinations[0])
            elif isinstance(destinations, str):
                main_dest = destinations
            else:
                main_dest = "the destination"
            
            external_context = await external_tools.get_recommendations(
                main_dest, 
                budget=form.budget or "standard",
                start_date=form.start_date.isoformat() if form.start_date else None,
                end_date=form.end_date.isoformat() if form.end_date else None
            )
        except Exception as e:
            print(f"Error fetching external context: {e}")
            external_context = "No external data available."


        

        try:
            messages = [
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": f"""HARD CONSTRAINTS:
{constraints}

SOFT PREFERENCES:
{preferences}

REAL-WORLD DATA (Use these for lodging and meals):
{external_context}

INSTRUCTIONS:
1. Generate a high-quality, balanced itinerary using REAL locations from the list above.
2. FULL COVERAGE: Fill the ENTIRE time range from DAILY START to DAILY END time. Do NOT stop early.
3. WEATHER & DISTANCE: Include a brief 'weather' summary for each day in the JSON. Estimate 'travel_distance_km' realistically between spots (typically 2-10km).
4. DO NOT use placeholders like "Local eatery" or "Drive to...".
5. Return ONLY RAW JSON matching the schema below. No markdown fences.

SCHEMA:
 {{
   "summary": "Short overview",
   "hotel_recommendations": [ {{ "name": "Name", "rating": "4-star", "location": "Area", "description": "Why", "price_range": "$$" }} ],
   "suggestions": [ {{ "title": "Place", "description": "Why", "icon": "..." }} ],
   "pro_tips": [ "Advice" ],
   "days": [ {{ 
     "day_number": 1, 
     "date": "YYYY-MM-DD", 
     "weather": "Sunny, 25°C",
     "total_distance_km": 0,
     "activities": [ {{ "time_slot": "HH:MM", "location": "Real Name", "description": "...", "travel_distance_km": 0 }} ] 
   }} ]
 }}"""}
            ]
            
            print(f"DEBUG: Sending request to LLM (Provider: {self.llm.provider})...")
            result = await self.llm.chat_json(messages, temperature=0.1, max_tokens=4096)
            print(f"DEBUG: LLM Response received: {str(result)[:100]}...")
            
            # Recalculate distances (Correction step)
            try:
                result = await external_tools.update_itinerary_distances(result)
            except Exception as e:
                print(f"Distance calculation failed: {e}")

            # Inject destination for fallback logic
            result["meta_destination"] = main_dest
            
            return self._parse_itinerary(result)
        except Exception as e:
            print(f"CRITICAL ERROR in Planner.generate: {e}")
            traceback.print_exc()
            # Return a fallback empty itinerary or re-raise to see 500
            # For debugging, we re-raise but now we have logs
            raise e

    
    async def answer_question(self, itinerary: Itinerary, question: str, destination: str = "your destination") -> str:
        """
        Answer a question about the generated itinerary.
        """
        context = f"Destination: {destination}\n"
        context += f"Trip Summary: {itinerary.summary}\n"
        for day in itinerary.days:
            context += f"Day {day.day_number}: {day.theme or 'Exploration'}\n"
            for act in day.activities:
                context += f"- {act.time_slot}: {act.location} ({act.activity_type.value})\n"
        
        messages = [
            {"role": "system", "content": f"You are a helpful travel assistant for {destination}. Answer the user's question based on the provided itinerary context. Keep answers regular length (2-3 sentences)."},
            {"role": "user", "content": f"USER QUESTION: {question}\n\nITINERARY CONTEXT:\n{context}"}
        ]
        
        return await self.llm.chat(messages, temperature=0.7, max_tokens=300)

    async def modify(
        self,
        current_itinerary: Itinerary,
        form: TravelForm,
        modification_request: str,
        soft_preferences: list[str] = None
    ) -> Itinerary:
        """
        Modify an existing itinerary based on user request.
        
        Args:
            current_itinerary: The current itinerary to modify
            form: The travel form (constraints still apply)
            modification_request: What the user wants to change
            soft_preferences: User preferences
            
        Returns:
            Modified Itinerary object
        """
        constraints = self._format_constraints(form)
        current_plan = json.dumps(current_itinerary.to_display_dict())
        preferences = "\n".join(soft_preferences) if soft_preferences else "None"
        
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"""HARD CONSTRAINTS (still apply):
{constraints}

CURRENT ITINERARY:
{current_plan}

MODIFICATION REQUEST:
{modification_request}

SOFT PREFERENCES:
{preferences}

Generate the modified itinerary. Remember: constraints cannot be violated even for modifications."""}
        ]
        
        result = await self.llm.chat_json(messages, temperature=0.7, max_tokens=3000)
        
        itinerary = self._parse_itinerary(result)
        itinerary.version = current_itinerary.version + 1
        return itinerary
    
    def _format_constraints(self, form: TravelForm) -> str:
        """Format form data as readable constraints."""
        filled = form.get_filled_fields()
        lines = []
        
        field_labels = {
            "trip_duration_days": "Trip Duration",
            "trip_duration_nights": "Nights",
            "traveler_count": "Number of Travelers",
            "group_type": "Group Type",
            "destinations": "Destinations",
            "start_date": "Start Date",
            "end_date": "End Date",
            "daily_start_time": "Daily Start Time",
            "daily_end_time": "Daily End Time",
            "weather_preference": "Weather Preference",
            "closed_days_restrictions": "Closed Days",
            "local_guidelines": "Local Guidelines",
            "max_travel_distance_km": "Max Daily Travel Distance",
            "sightseeing_pace": "Sightseeing Pace",
            "cab_pickup_required": "Cab Pickup Required",
            "hotel_checkin_time": "Hotel Check-in Time",
            "hotel_checkout_time": "Hotel Check-out Time",
            "traffic_consideration": "Consider Traffic",
            "travel_mode": "Travel Mode",
            "budget": "Budget Level",
        }
        
        for field, value in filled.items():
            label = field_labels.get(field, field)
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            lines.append(f"- {label}: {value}")
        
        return "\n".join(lines)
    
    def _parse_itinerary(self, data: dict) -> Itinerary:
        """Parse LLM response into Itinerary object."""
        days = []
        
        # Parse Hotel Recommendations
        from ..models.itinerary import HotelRecommendation
        hotel_recs = []
        for h in data.get("hotel_recommendations", []):
            try:
                hotel_recs.append(HotelRecommendation(
                    name=h.get("name", "Unknown Hotel"),
                    rating=h.get("rating", "Standard"),
                    location=h.get("location", "City Center"),
                    description=h.get("description", ""),
                    price_range=h.get("price_range")
                ))
            except Exception as e:
                print(f"Skipping invalid hotel rec: {e}")

        # Fallback: If no hotels from LLM, fetch from Local DB
        if not hotel_recs:
             print("DEBUG: No hotels from LLM, fetching from Local DB...")
             try:
                 # Try to guess destination from summary or first day
                 # This is tricky without explicit dest, but we can try to find a known city
                 # Or better, pass destination to _parse_itinerary (requires signature change)
                 # For now, let's look at the first activity location or summary
                 
                 # Better approach: We can't easily change signature safely across all calls right now
                 # But we can access the global instance of local_db
                 from .local_database import local_db
                 
                 # Heuristic: Try to find a city name in the summary
                 # This is weak. Ideally, we should pass the destination.
                 # Let's fallback to "Indore" if we detect it, or just leave it empty if we can't be sure.
                 # Wait, 'generate' method has 'form.destinations'. 
                 # We can inject 'meta_destination' into the data dict in 'generate' before calling parse?
                 pass
             except Exception as e:
                 print(f"Hotel injection failed: {e}")


        # Fallback: If no hotels from LLM, fetch from Local DB
        if not hotel_recs:
             dest = data.get("meta_destination")
             if dest:
                 print(f"DEBUG: No hotels from LLM, fetching for {dest}...")
                 try:
                     from .local_database import local_db
                     # Try exact match or fuzzy
                     db_hotels = local_db.get_hotels(dest)
                     if not db_hotels:
                         # Try finding official name
                         status = local_db.get_city_status(dest)
                         if status['found']:
                             db_hotels = local_db.get_hotels(status['official_name'])
                     
                     for h in db_hotels[:3]:
                         hotel_recs.append(HotelRecommendation(
                             name=h.get('name'),
                             rating=h.get('category', 'Standard'),
                             location=f"{h.get('lat')}, {h.get('lon')}",
                             description="Top rated local stay.",
                             price_range="$$"
                         ))
                 except Exception as e:
                     print(f"Hotel fallback failed: {e}")

        for day_data in data.get("days", []):
            activities = []
            for act_data in day_data.get("activities", []):
                location = act_data.get("location", "Unknown")
                desc = act_data.get("description", "")
                
                # Aggressive Anti-Filler Logic: Skip 'Travel', 'Drive', or 'Hotel' blocks
                loc_lower = location.lower()
                desc_lower = desc.lower()
                
                # Check for Hotel/Check-in explicitly
                is_hotel = any(x in loc_lower for x in ["check-in", "check in", "hotel", "resort", "stay at"]) or \
                           any(x in desc_lower for x in ["check-in", "check in", "hotel stay", "checking in"])
                
                if is_hotel:
                    print(f"DEBUG: Filtered out hotel activity: {location}")
                    continue

                is_filler = any(x in loc_lower for x in ["travel to", "drive to", "walking to", "transit"]) or \
                            any(x in desc_lower for x in ["travel to", "drive to", "walking to", "heading to"])
                
                if is_filler and act_data.get("activity_type", "").lower() != "sightseeing":
                     # Double check: if it's marked as sightseeing but says travel, it's filler
                     continue
                if is_filler:
                    continue
                
                # Skip transit hubs as sightseeing
                if "railway station" in loc_lower or "airport" in loc_lower or "bus stand" in loc_lower:
                    if "explore" in desc_lower or "stroll" in desc_lower:
                        continue

                activity_type_str = act_data.get("activity_type", "sightseeing")
                try:
                    activity_type = ActivityType(activity_type_str.lower())
                except ValueError:
                    activity_type = ActivityType.SIGHTSEEING
                
                activities.append(Activity(
                    time_slot=act_data.get("time_slot") or act_data.get("time") or "09:00 - 10:00",
                    location=act_data.get("location", "Unknown"),
                    activity_type=activity_type,
                    description=act_data.get("description", ""),
                    travel_distance_km=float(act_data.get("travel_distance_km", 0)),
                    duration_minutes=int(act_data.get("duration_minutes", 60)),
                    notes=act_data.get("notes")
                ))
            
            day = DayPlan(
                day_number=day_data.get("day_number", 1),
                date=day_data.get("date", datetime.now().strftime("%Y-%m-%d")),
                theme=day_data.get("theme"),
                activities=activities,
                total_distance_km=float(day_data.get("total_distance_km", 0)),
                weather=day_data.get("weather")
            )
            day.calculate_total_distance()
            days.append(day)
        
        return Itinerary(
            summary=data.get("summary", "Travel itinerary"),
            days=days,
            hotel_recommendations=hotel_recs,
            soft_preferences_applied=data.get("soft_preferences_applied", []),
            soft_preferences_ignored=data.get("soft_preferences_ignored", []),
            changes_made=data.get("changes_made", []),
            change_summary=data.get("change_summary", ""),
            suggestions=data.get("suggestions", []),
            pro_tips=data.get("pro_tips", [])
        )


# Global planner instance
planner: Optional[ItineraryPlanner] = None


def get_planner() -> ItineraryPlanner:
    """Get or create the global planner."""
    global planner
    if planner is None:
        planner = ItineraryPlanner()
    return planner
