"""
API Routes for Travel Planner.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..models.session import Session, session_store
from ..services.flow_controller import get_flow_controller, ResponseType


router = APIRouter(prefix="/api", tags=["travel-planner"])


# Request/Response Models
class CreateSessionResponse(BaseModel):
    session_id: str
    message: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    response_type: str
    message: str
    form_status: Optional[dict] = None
    itinerary: Optional[dict] = None


class FormStatusResponse(BaseModel):
    filled_fields: dict
    missing_fields: list[str]
    is_complete: bool
    is_locked: bool


class FormUpdateRequest(BaseModel):
    session_id: str
    field_updates: dict


# Endpoints

@router.post("/session", response_model=CreateSessionResponse)
async def create_session():
    """Create a new chat session."""
    session = session_store.create()
    
    # Add welcome message
    welcome = """👋 **Welcome to the Travel Planner!**

I'll help you create a personalized travel itinerary. Just tell me about your trip naturally, and I'll collect all the details.

For example, you can say:
- "I want to visit Jaipur for 3 days with my family"
- "Planning a solo trip to Goa from March 15 to 20"

What destination are you dreaming of? 🌍"""
    
    session.add_message("assistant", welcome)
    session_store.update(session)
    
    return CreateSessionResponse(
        session_id=session.session_id,
        message=welcome
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Send a chat message and get response."""
    session = session_store.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    flow = get_flow_controller()
    
    try:
        response_type, message, data = await flow.process_message(
            session,
            request.message
        )
        
        # Build response
        response = ChatResponse(
            response_type=response_type.value,
            message=message,
            form_status=session.get_form_summary()
        )
        
        # Include itinerary if available
        if response_type in (ResponseType.ITINERARY, ResponseType.MODIFICATION):
            response.itinerary = data
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@router.get("/form/{session_id}", response_model=FormStatusResponse)
async def get_form_status(session_id: str):
    """Get the current form status."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    summary = session.get_form_summary()
    return FormStatusResponse(**summary)


@router.post("/form/{session_id}")
async def submit_and_lock_form(session_id: str, form_data: dict):
    """Submit form data and lock the form (Form-First Architecture)."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.form_locked:
        raise HTTPException(status_code=400, detail="Form is already locked")
    
    # Validate required fields
    required = [
        "destinations", "group_type", "traveler_count",
        "trip_duration_days", "start_date", "end_date",
        "daily_start_time", "daily_end_time", "sightseeing_pace", "travel_mode"
    ]
    
    missing = [f for f in required if not form_data.get(f)]
    if missing:
        raise HTTPException(
            status_code=400, 
            detail=f"Missing required fields: {', '.join(missing)}"
        )
    
    # Update form with all data
    session.update_form(form_data)
    
    # Lock the form
    session.form_locked = True
    session_store.update(session)
    
    return {
        "success": True,
        "form_locked": True,
        "form_status": session.get_form_summary()
    }


@router.put("/form/{session_id}")
async def update_form_directly(session_id: str, request: FormUpdateRequest):
    """Update form fields directly (only before locking)."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.form_locked:
        raise HTTPException(status_code=400, detail="Form is locked. Cannot modify.")
    
    session.update_form(request.field_updates, overwrite=True)
    session_store.update(session)
    
    return {
        "success": True,
        "form_status": session.get_form_summary()
    }


@router.get("/itinerary/{session_id}")
async def get_itinerary(session_id: str):
    """Get the current itinerary."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    current = session.get_current_itinerary()
    if not current:
        return {"itinerary": None, "message": "No itinerary generated yet"}
    
    return {
        "itinerary": current.to_display_dict(),
        "total_versions": len(session.itineraries)
    }


@router.get("/itinerary/{session_id}/versions")
async def get_all_versions(session_id: str):
    """Get all itinerary versions."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "versions": [
            {
                "version": it.version,
                "created_at": it.created_at.isoformat(),
                "summary": it.summary
            }
            for it in session.itineraries
        ]
    }


@router.get("/messages/{session_id}")
async def get_messages(session_id: str):
    """Get all chat messages for a session."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in session.messages
        ]
    }
