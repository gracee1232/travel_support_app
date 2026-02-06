"""Tests for conversation flow."""
import pytest
from app.models.session import Session, SessionState, session_store
from app.models.form_schema import TravelForm, GroupType, SightseeingPace, TravelMode
from datetime import date, time


class TestSession:
    """Test session management."""
    
    def test_session_creation(self):
        """Test creating a new session."""
        session = Session()
        
        assert session.session_id is not None
        assert session.state == SessionState.COLLECTING
        assert session.form_locked == False
        assert len(session.messages) == 0
        assert len(session.itineraries) == 0
    
    def test_add_message(self):
        """Test adding messages to session."""
        session = Session()
        
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there!")
        
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[1].content == "Hi there!"
    
    def test_form_update(self):
        """Test updating form through session."""
        session = Session()
        
        session.update_form({
            "trip_duration_days": 3,
            "destinations": ["Jaipur"]
        })
        
        assert session.form.trip_duration_days == 3
        assert session.form.destinations == ["Jaipur"]
    
    def test_form_completion_triggers_state_change(self):
        """Test that completing form changes session state."""
        session = Session()
        
        # Fill all required fields
        complete_data = {
            "trip_duration_days": 3,
            "trip_duration_nights": 2,
            "traveler_count": 2,
            "group_type": "couple",
            "destinations": ["Jaipur"],
            "start_date": "2026-03-15",
            "end_date": "2026-03-17",
            "daily_start_time": "09:00",
            "daily_end_time": "18:00",
            "weather_preference": "any",
            "closed_days_restrictions": [],
            "local_guidelines": "None",
            "max_travel_distance_km": 100,
            "sightseeing_pace": "moderate",
            "cab_pickup_required": True,
            "hotel_checkin_time": "14:00",
            "hotel_checkout_time": "11:00",
            "traffic_consideration": True,
            "travel_mode": "mixed"
        }
        
        session.update_form(complete_data)
        
        assert session.form.is_complete()
        assert session.state == SessionState.FORM_COMPLETE
    
    def test_form_lock(self):
        """Test locking the form."""
        session = Session()
        session.lock_form()
        
        assert session.form_locked == True
        assert session.state == SessionState.PLANNING
    
    def test_soft_preferences(self):
        """Test adding soft preferences."""
        session = Session()
        
        session.add_soft_preference("prefer temples")
        session.add_soft_preference("avoid walking")
        session.add_soft_preference("prefer temples")  # Duplicate
        
        assert len(session.soft_preferences) == 2
        assert "prefer temples" in session.soft_preferences


class TestSessionStore:
    """Test session store operations."""
    
    def test_create_and_get(self):
        """Test creating and retrieving sessions."""
        store = session_store
        
        session = store.create()
        retrieved = store.get(session.session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    def test_get_nonexistent(self):
        """Test getting non-existent session returns None."""
        store = session_store
        
        result = store.get("nonexistent-id")
        assert result is None
    
    def test_update(self):
        """Test updating a session."""
        store = session_store
        
        session = store.create()
        session.add_message("user", "Test")
        store.update(session)
        
        retrieved = store.get(session.session_id)
        assert len(retrieved.messages) == 1
