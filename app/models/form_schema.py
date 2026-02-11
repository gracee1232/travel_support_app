"""
Travel Form Schema - Mandatory Form Fields (Hard Constraints).
All fields must be filled before itinerary generation.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import date, time
from enum import Enum


class GroupType(str, Enum):
    """Travel group types."""
    SOLO = "solo"
    COUPLE = "couple"
    FAMILY = "family"
    FRIENDS = "friends"
    GROUP = "group"
    BUSINESS = "business"


class WeatherPreference(str, Enum):
    """Weather preference options."""
    ANY = "any"
    SUNNY = "sunny"
    CLOUDY = "cloudy"
    MILD = "mild"


class SightseeingPace(str, Enum):
    """Sightseeing pace options."""
    RELAXED = "relaxed"
    MODERATE = "moderate"
    PACKED = "packed"


class TravelMode(str, Enum):
    """Mode of travel."""
    DRIVING = "driving"
    WALKING = "walking"
    PUBLIC_TRANSIT = "public_transport"
    MIXED = "mixed"


class BudgetLevel(str, Enum):
    """Trip budget levels."""
    ECONOMY = "economy"
    STANDARD = "standard"
    LUXURY = "luxury"
    LAVISH = "lavish"


class TravelForm(BaseModel):
    """
    Mandatory travel form - The SOURCE OF TRUTH.
    All fields are required for itinerary generation.
    """
    # Trip Duration
    trip_duration_days: Optional[int] = Field(
        None, ge=1, le=30,
        description="Number of days for the trip"
    )
    trip_duration_nights: Optional[int] = Field(
        None, ge=0, le=30,
        description="Number of nights for the trip"
    )
    
    # Travelers
    traveler_count: Optional[int] = Field(
        None, ge=1, le=50,
        description="Number of travelers"
    )
    group_type: Optional[GroupType] = Field(
        None,
        description="Type of travel group"
    )
    
    # Destinations
    destinations: Optional[list[str]] = Field(
        None,
        description="List of destinations to visit"
    )
    
    # Dates and Times
    start_date: Optional[date] = Field(
        None,
        description="Trip start date"
    )
    end_date: Optional[date] = Field(
        None,
        description="Trip end date"
    )
    daily_start_time: Optional[time] = Field(
        None,
        description="Daily activity start time"
    )
    daily_end_time: Optional[time] = Field(
        None,
        description="Daily activity end time"
    )
    
    # Preferences
    weather_preference: Optional[WeatherPreference] = Field(
        None,
        description="Preferred weather conditions"
    )
    
    # Restrictions
    closed_days_restrictions: Optional[list[str]] = Field(
        None,
        description="Days or dates when certain places are closed"
    )
    local_guidelines: Optional[str] = Field(
        None,
        description="Local or government guidelines to consider"
    )
    
    # Travel Constraints
    max_travel_distance_km: Optional[int] = Field(
        None, ge=1, le=500,
        description="Maximum travel distance per day in kilometers"
    )
    sightseeing_pace: Optional[SightseeingPace] = Field(
        None,
        description="Preferred pace of sightseeing"
    )
    
    # Logistics
    cab_pickup_required: Optional[bool] = Field(
        None,
        description="Whether cab pickup is required"
    )
    hotel_checkin_time: Optional[time] = Field(
        None,
        description="Hotel check-in time"
    )
    hotel_checkout_time: Optional[time] = Field(
        None,
        description="Hotel check-out time"
    )
    traffic_consideration: Optional[bool] = Field(
        None,
        description="Whether to consider traffic in planning"
    )
    travel_mode: Optional[TravelMode] = Field(
        None,
        description="Preferred mode of travel"
    )
    budget: Optional[BudgetLevel] = Field(
        None,
        description="Trip budget level"
    )

    @field_validator('destinations', mode='before')
    @classmethod
    def validate_destinations(cls, v):
        if v is not None and len(v) == 0:
            return None
        return v

    def get_missing_fields(self) -> list[str]:
        """Return list of field names that are still None."""
        missing = []
        for field_name, field_info in self.model_fields.items():
            value = getattr(self, field_name)
            if value is None:
                missing.append(field_name)
        return missing
    
    def is_complete(self) -> bool:
        """Check if all mandatory fields are filled."""
        return len(self.get_missing_fields()) == 0
    
    def get_filled_fields(self) -> dict:
        """Return dict of fields that have values."""
        filled = {}
        for field_name in self.model_fields:
            value = getattr(self, field_name)
            if value is not None:
                if isinstance(value, Enum):
                    filled[field_name] = value.value
                elif isinstance(value, (date, time)):
                    filled[field_name] = value.isoformat()
                else:
                    filled[field_name] = value
        return filled
    
    def merge_extracted(self, extracted: dict) -> "TravelForm":
        """Merge extracted data into form, only updating None fields."""
        current_data = self.model_dump()
        for key, value in extracted.items():
            if key in current_data and value is not None:
                # Only update if current value is None
                if current_data[key] is None:
                    current_data[key] = value
        return TravelForm(**current_data)

    def update_fields(self, updates: dict) -> "TravelForm":
        """Update fields with new values (overwriting existing)."""
        current_data = self.model_dump()
        for key, value in updates.items():
             # Basic validation/cleaning could happen here
             if key in current_data:
                 current_data[key] = value
        return TravelForm(**current_data)


# JSON Schema for form validation (used by backend)
TRAVEL_FORM_SCHEMA = {
    "type": "object",
    "properties": {
        "trip_duration_days": {"type": "integer", "minimum": 1, "maximum": 30},
        "trip_duration_nights": {"type": "integer", "minimum": 0, "maximum": 30},
        "traveler_count": {"type": "integer", "minimum": 1, "maximum": 50},
        "group_type": {"type": "string", "enum": ["solo", "couple", "family", "friends", "group", "business"]},
        "destinations": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "start_date": {"type": "string", "format": "date"},
        "end_date": {"type": "string", "format": "date"},
        "daily_start_time": {"type": "string", "format": "time"},
        "daily_end_time": {"type": "string", "format": "time"},
        "weather_preference": {"type": "string", "enum": ["any", "sunny", "cloudy", "mild"]},
        "closed_days_restrictions": {"type": "array", "items": {"type": "string"}},
        "local_guidelines": {"type": "string"},
        "max_travel_distance_km": {"type": "integer", "minimum": 1, "maximum": 500},
        "sightseeing_pace": {"type": "string", "enum": ["relaxed", "moderate", "packed"]},
        "cab_pickup_required": {"type": "boolean"},
        "hotel_checkin_time": {"type": "string", "format": "time"},
        "hotel_checkout_time": {"type": "string", "format": "time"},
        "traffic_consideration": {"type": "boolean"},
        "travel_mode": {"type": "string", "enum": ["driving", "walking", "public_transport", "mixed"]},
        "budget": {"type": "string", "enum": ["economy", "standard", "luxury", "lavish"]}
    },
    "required": [
        "trip_duration_days", "traveler_count", "group_type",
        "destinations", "start_date", "end_date", "daily_start_time", "daily_end_time",
        "max_travel_distance_km", "sightseeing_pace",
        "cab_pickup_required", "traffic_consideration", "travel_mode", "budget"
    ]
}


# Human-readable field descriptions for follow-up questions
FIELD_QUESTIONS = {
    "trip_duration_days": "How many days will your trip be?",
    "trip_duration_nights": "How many nights will you stay?",
    "traveler_count": "How many people will be traveling?",
    "group_type": "What type of group is this? (solo, couple, family, or group)",
    "destinations": "Which destinations would you like to visit?",
    "start_date": "What is your trip start date?",
    "end_date": "What is your trip end date?",
    "daily_start_time": "What time would you like to start your activities each day?",
    "daily_end_time": "What time would you like to end your activities each day?",
    "weather_preference": "Do you have a weather preference? (any, sunny, cloudy, or mild)",
    "closed_days_restrictions": "Are there any days or dates when certain places might be closed that we should consider?",
    "local_guidelines": "Are there any local or government guidelines we should consider?",
    "max_travel_distance_km": "What's the maximum distance you'd like to travel per day (in kilometers)?",
    "sightseeing_pace": "What pace of sightseeing do you prefer? (relaxed, moderate, or packed)",
    "cab_pickup_required": "Do you need cab pickup services?",
    "hotel_checkin_time": "What time is your hotel check-in?",
    "hotel_checkout_time": "What time is your hotel check-out?",
    "traffic_consideration": "Should we consider traffic in the planning?",
    "travel_mode": "What's your preferred mode of travel? (driving, walking, public transit, or mixed)",
    "budget": "What is your budget level? (economy, standard, luxury, or lavish)"
}
