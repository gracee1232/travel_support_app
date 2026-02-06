"""Tests for form validation."""
import pytest
from datetime import date, time
from app.models.form_schema import TravelForm, GroupType, SightseeingPace, TravelMode


class TestTravelForm:
    """Test TravelForm validation and methods."""
    
    def test_empty_form_has_all_missing(self):
        """Empty form should have all fields missing."""
        form = TravelForm()
        missing = form.get_missing_fields()
        assert len(missing) == 19  # All mandatory fields
        assert not form.is_complete()
    
    def test_partial_form(self):
        """Partial form should track missing fields correctly."""
        form = TravelForm(
            trip_duration_days=3,
            destinations=["Jaipur", "Udaipur"],
            traveler_count=2
        )
        
        missing = form.get_missing_fields()
        assert "trip_duration_days" not in missing
        assert "destinations" not in missing
        assert "traveler_count" not in missing
        assert "start_date" in missing
        assert not form.is_complete()
    
    def test_complete_form(self):
        """Complete form should pass validation."""
        form = TravelForm(
            trip_duration_days=3,
            trip_duration_nights=2,
            traveler_count=2,
            group_type=GroupType.COUPLE,
            destinations=["Jaipur"],
            start_date=date(2026, 3, 15),
            end_date=date(2026, 3, 17),
            daily_start_time=time(9, 0),
            daily_end_time=time(18, 0),
            weather_preference="any",
            closed_days_restrictions=[],
            local_guidelines="None",
            max_travel_distance_km=100,
            sightseeing_pace=SightseeingPace.MODERATE,
            cab_pickup_required=True,
            hotel_checkin_time=time(14, 0),
            hotel_checkout_time=time(11, 0),
            traffic_consideration=True,
            travel_mode=TravelMode.MIXED
        )
        
        assert form.is_complete()
        assert len(form.get_missing_fields()) == 0
    
    def test_merge_extracted(self):
        """Test merging extracted data into form."""
        form = TravelForm(trip_duration_days=3)
        
        extracted = {
            "destinations": ["Goa"],
            "traveler_count": 4,
            "trip_duration_days": 5  # Should NOT override existing
        }
        
        merged = form.merge_extracted(extracted)
        
        # New fields should be set
        assert merged.destinations == ["Goa"]
        assert merged.traveler_count == 4
        # Existing field should NOT be overwritten
        assert merged.trip_duration_days == 3
    
    def test_get_filled_fields(self):
        """Test getting filled fields as dict."""
        form = TravelForm(
            trip_duration_days=5,
            group_type=GroupType.FAMILY,
            destinations=["Mumbai", "Pune"]
        )
        
        filled = form.get_filled_fields()
        
        assert filled["trip_duration_days"] == 5
        assert filled["group_type"] == "family"
        assert filled["destinations"] == ["Mumbai", "Pune"]
        assert "start_date" not in filled
    
    def test_validation_constraints(self):
        """Test field validation constraints."""
        # trip_duration_days must be >= 1
        with pytest.raises(ValueError):
            TravelForm(trip_duration_days=0)
        
        # traveler_count must be >= 1
        with pytest.raises(ValueError):
            TravelForm(traveler_count=0)
        
        # max_travel_distance_km must be <= 500
        with pytest.raises(ValueError):
            TravelForm(max_travel_distance_km=1000)
