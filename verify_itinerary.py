
import requests
import json

BASE_URL = "http://localhost:8001/api"

def run_test():
    resp = requests.post(f"{BASE_URL}/session", json={})
    session_id = resp.json()["session_id"]
    form_data = {
        "session_id": session_id,
        "field_updates": {
            "destinations": ["Paris"], "trip_duration_days": 2, "trip_duration_nights": 1,
            "group_type": "couple", "traveler_count": 2, "start_date": "2024-06-01",
            "end_date": "2024-06-02", "daily_start_time": "10:00", "daily_end_time": "20:00",
            "weather_preference": "any", "closed_days_restrictions": [], "local_guidelines": "None",
            "max_travel_distance_km": 15, "sightseeing_pace": "moderate", "cab_pickup_required": False,
            "hotel_checkin_time": "14:00", "hotel_checkout_time": "11:00", "traffic_consideration": False,
            "travel_mode": "public_transport",
            "budget": "luxury"
        }
    }
    requests.put(f"{BASE_URL}/form/{session_id}", json=form_data)
    chat_payload = {"session_id": session_id, "message": "Plan my luxury trip now"}
    resp = requests.post(f"{BASE_URL}/chat", json=chat_payload)
    
    if resp.status_code == 200:
        itinerary = resp.json().get("itinerary", {})
        print(f"\nSummary: {itinerary.get('summary')}")
        print("\nSuggestions:")
        for s in itinerary.get("suggestions", []):
            print(f"- {s.get('title')}: {s.get('description')} ({s.get('icon')})")
        print("\nPro Tips:")
        for t in itinerary.get("pro_tips", []):
            print(f"- {t}")
    else:
        print("Error:", resp.text)

if __name__ == "__main__":
    run_test()
