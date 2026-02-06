"""Tests for information extractor."""
import pytest
from unittest.mock import AsyncMock, patch


class TestInformationExtractor:
    """Test the extraction logic."""
    
    @pytest.mark.asyncio
    async def test_extraction_cleaning(self):
        """Test that extraction cleans data properly."""
        from app.services.extractor import InformationExtractor
        
        extractor = InformationExtractor()
        
        # Test cleaning logic directly
        raw_data = {
            "trip_duration_days": "3",  # String should become int
            "destinations": "Jaipur",   # String should become list
            "cab_pickup_required": "yes",  # String should become bool
            "traveler_count": 2,
            "random_field": "ignored"   # Unknown fields should be ignored
        }
        
        cleaned = extractor._clean_extraction(raw_data)
        
        assert cleaned["trip_duration_days"] == 3
        assert cleaned["destinations"] == ["Jaipur"]
        assert cleaned["cab_pickup_required"] == True
        assert cleaned["traveler_count"] == 2
        assert "random_field" not in cleaned
    
    @pytest.mark.asyncio
    async def test_soft_preferences_extraction(self):
        """Test that soft preferences are extracted separately."""
        from app.services.extractor import InformationExtractor
        
        extractor = InformationExtractor()
        
        raw_data = {
            "destinations": ["Goa"],
            "soft_preferences": ["vegetarian food", "avoid crowded places"]
        }
        
        cleaned = extractor._clean_extraction(raw_data)
        
        assert "soft_preferences" in cleaned
        assert len(cleaned["soft_preferences"]) == 2
    
    @pytest.mark.asyncio
    async def test_empty_values_ignored(self):
        """Test that empty/null values are not included."""
        from app.services.extractor import InformationExtractor
        
        extractor = InformationExtractor()
        
        raw_data = {
            "trip_duration_days": 3,
            "destinations": [],  # Empty list should be ignored
            "local_guidelines": "",  # Empty string should be ignored
            "traveler_count": None  # None should be ignored
        }
        
        cleaned = extractor._clean_extraction(raw_data)
        
        assert cleaned["trip_duration_days"] == 3
        assert "destinations" not in cleaned
        assert "local_guidelines" not in cleaned
        assert "traveler_count" not in cleaned
