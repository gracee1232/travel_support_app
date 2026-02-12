"""
Itinerary models - Structured output for travel plans.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class ActivityType(str, Enum):
    """Types of activities in an itinerary."""
    SIGHTSEEING = "sightseeing"
    MEAL = "meal"
    TRAVEL = "travel"
    REST = "rest"
    SHOPPING = "shopping"
    ADVENTURE = "adventure"
    CULTURAL = "cultural"
    CHECKIN = "checkin"
    CHECKOUT = "checkout"


class Activity(BaseModel):
    """A single activity in the itinerary."""
    time_slot: str = Field(
        ...,
        description="Time range, e.g., '09:00 - 11:00'"
    )
    location: str = Field(
        ...,
        description="Name of the place/location"
    )
    activity_type: ActivityType = Field(
        ...,
        description="Type of activity"
    )
    description: str = Field(
        ...,
        description="Brief description of the activity"
    )
    travel_distance_km: float = Field(
        default=0.0,
        ge=0,
        description="Distance to travel to this location"
    )
    duration_minutes: int = Field(
        default=60,
        ge=0,
        description="Duration of the activity in minutes"
    )
    notes: Optional[str] = Field(
        None,
        description="Additional notes or tips"
    )


class DayPlan(BaseModel):
    """Plan for a single day."""
    day_number: int = Field(
        ...,
        ge=1,
        description="Day number in the trip"
    )
    date: str = Field(
        ...,
        description="Date for this day (YYYY-MM-DD)"
    )
    theme: Optional[str] = Field(
        None,
        description="Theme or focus for the day"
    )
    activities: list[Activity] = Field(
        default_factory=list,
        description="List of activities for the day"
    )
    total_distance_km: float = Field(
        default=0.0,
        ge=0,
        description="Total travel distance for the day"
    )
    weather: Optional[str] = Field(
        None,
        description="Weather snippet for this day"
    )
    
    def calculate_total_distance(self) -> float:
        """Calculate total distance from activities."""
        self.total_distance_km = sum(a.travel_distance_km for a in self.activities)
        return self.total_distance_km


class HotelRecommendation(BaseModel):
    """A recommended hotel."""
    name: str = Field(..., description="Name of the hotel")
    rating: str = Field(..., description="Star rating or category (e.g. '4-star', 'Budget')")
    location: str = Field(..., description="Location or area")
    description: str = Field(..., description="Brief description or why it matches the budget")
    price_range: Optional[str] = Field(None, description="Estimated price range")


class Itinerary(BaseModel):
    """Complete travel itinerary."""
    version: int = Field(
        default=1,
        ge=1,
        description="Version number of the itinerary"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this itinerary was created"
    )
    summary: str = Field(
        default="",
        description="Brief summary of the entire trip"
    )
    # Hotel Recommendations (Separated from daily plans)
    hotel_recommendations: list[HotelRecommendation] = Field(
        default_factory=list,
        description="List of recommended hotels for the trip"
    )
    days: list[DayPlan] = Field(
        default_factory=list,
        description="Day-wise plans"
    )
    soft_preferences_applied: list[str] = Field(
        default_factory=list,
        description="List of soft preferences that were applied"
    )
    soft_preferences_ignored: list[str] = Field(
        default_factory=list,
        description="List of soft preferences ignored due to constraint conflicts"
    )
    changes_made: list[str] = Field(
        default_factory=list,
        description="List of changes made in this version (for modifications)"
    )
    change_summary: str = Field(
        default="",
        description="Human-readable summary of what changed in this version"
    )
    
    # Personalization
    suggestions: list[dict] = Field(
        default_factory=list,
        description="List of suggestions for the user (e.g., alternative activities, nearby attractions)"
    )
    pro_tips: list[str] = Field(
        default_factory=list,
        description="List of pro tips for the trip (e.g., local customs, best times to visit)"
    )
    
    def get_total_distance(self) -> float:
        """Get total distance for the entire trip."""
        return sum(day.total_distance_km for day in self.days)
    
    def to_display_dict(self) -> dict:
        """Convert to display-friendly dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "summary": self.summary,
            "total_days": len(self.days),
            "total_distance_km": self.get_total_distance(),
            "changes_made": self.changes_made,
            "change_summary": self.change_summary,
            "suggestions": self.suggestions,
            "pro_tips": self.pro_tips,
            "days": [
                {
                    "day_number": day.day_number,
                    "date": day.date,
                    "theme": day.theme,
                    "weather": day.weather,
                    "total_distance_km": day.total_distance_km,
                    "activities": [
                        {
                            "time": act.time_slot,
                            "location": act.location,
                            "type": act.activity_type.value,
                            "description": act.description,
                            "distance_km": act.travel_distance_km,
                            "notes": act.notes
                        }
                        for act in day.activities
                    ]
                }
                for day in self.days
            ]
        }
