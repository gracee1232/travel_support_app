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


PLANNER_SYSTEM_PROMPT = """You are a travel itinerary planner. Generate a realistic, day-wise travel itinerary.

YOUR JOB:
1. Create a detailed day-by-day plan
2. Ensure all activities fit within the given time constraints
3. Never exceed maximum travel distances
4. Create realistic, achievable schedules

STRICT RULES - FOLLOW ALL HARD CONSTRAINTS:
- NEVER exceed max_travel_distance_km per day
- ALWAYS respect daily_start_time and daily_end_time
- Match the sightseeing_pace (relaxed=3-4 activities, moderate=5-6, packed=7-8 per day)
- Account for hotel check-in on first day and check-out on last day
- If traffic_consideration is true, add buffer time for travel
- Consider the travel_mode for realistic transit times

SOFT PREFERENCES:
Apply these ONLY if they don't conflict with hard constraints. If a preference conflicts, ignore it.

OUTPUT FORMAT - Return ONLY valid JSON:
{
  "summary": "Brief 1-2 sentence trip summary",
  "days": [
    {
      "day_number": 1,
      "date": "YYYY-MM-DD",
      "theme": "Day theme or focus",
      "activities": [
        {
          "time_slot": "HH:MM - HH:MM",
          "location": "Place name",
          "activity_type": "sightseeing|meal|travel|rest|shopping|adventure|cultural|checkin|checkout",
          "description": "What to do there",
          "travel_distance_km": 0.0,
          "duration_minutes": 60,
          "notes": "Optional tips"
        }
      ],
      "total_distance_km": 0.0
    }
  ],
  "soft_preferences_applied": ["list of preferences that were used"],
  "soft_preferences_ignored": ["list of preferences ignored due to conflicts"]
}"""


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
        
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"""HARD CONSTRAINTS (MUST follow):
{constraints}

SOFT PREFERENCES (optional, apply if no conflict):
{preferences}

Generate the itinerary now."""}
        ]
        
        result = await self.llm.chat_json(messages, temperature=0.7, max_tokens=3000)
        
        return self._parse_itinerary(result)
    
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
        
        for day_data in data.get("days", []):
            activities = []
            for act_data in day_data.get("activities", []):
                activity_type_str = act_data.get("activity_type", "sightseeing")
                try:
                    activity_type = ActivityType(activity_type_str.lower())
                except ValueError:
                    activity_type = ActivityType.SIGHTSEEING
                
                activities.append(Activity(
                    time_slot=act_data.get("time_slot", "09:00 - 10:00"),
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
                total_distance_km=float(day_data.get("total_distance_km", 0))
            )
            day.calculate_total_distance()
            days.append(day)
        
        return Itinerary(
            summary=data.get("summary", "Travel itinerary"),
            days=days,
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
