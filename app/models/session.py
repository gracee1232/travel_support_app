"""
Session management - Tracks conversation state and form progress.
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid

from .form_schema import TravelForm
from .itinerary import Itinerary


class SessionState(str, Enum):
    """Current state of the session."""
    COLLECTING = "collecting"  # Collecting form data
    FORM_COMPLETE = "form_complete"  # Form complete, ready to plan
    PLANNING = "planning"  # Generating itinerary
    ITERATING = "iterating"  # User requesting changes
    COMPLETE = "complete"  # Itinerary finalized


class ChatMessage(BaseModel):
    """A single message in the conversation."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.now)


class Session(BaseModel):
    """User session with form state and conversation history."""
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique session identifier"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Session creation time"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Last update time"
    )
    
    # Session State
    state: SessionState = Field(
        default=SessionState.COLLECTING,
        description="Current session state"
    )
    form_locked: bool = Field(
        default=False,
        description="Whether the form is locked for changes"
    )
    
    # Travel Form (Hard Constraints)
    form: TravelForm = Field(
        default_factory=TravelForm,
        description="The mandatory travel form"
    )
    
    # Soft Preferences (Optional)
    soft_preferences: list[str] = Field(
        default_factory=list,
        description="User's optional preferences from chat"
    )
    
    # Conversation History
    messages: list[ChatMessage] = Field(
        default_factory=list,
        description="Chat history"
    )
    
    # Itinerary Versions
    itineraries: list[Itinerary] = Field(
        default_factory=list,
        description="All itinerary versions"
    )
    
    def add_message(self, role: str, content: str) -> ChatMessage:
        """Add a message to the conversation."""
        msg = ChatMessage(role=role, content=content)
        self.messages.append(msg)
        self.updated_at = datetime.now()
        return msg
    
    def add_soft_preference(self, preference: str):
        """Add a soft preference."""
        if preference and preference not in self.soft_preferences:
            self.soft_preferences.append(preference)
            self.updated_at = datetime.now()
    
    def update_form(self, extracted_data: dict, overwrite: bool = False):
        """Merge extracted data into form."""
        if overwrite:
            self.form = self.form.update_fields(extracted_data)
        else:
            self.form = self.form.merge_extracted(extracted_data)
        
        self.updated_at = datetime.now()
        
        # Check if form is now complete
        if self.form.is_complete() and self.state == SessionState.COLLECTING:
            self.state = SessionState.FORM_COMPLETE
    
    def lock_form(self):
        """Lock the form to prevent further changes."""
        self.form_locked = True
        self.state = SessionState.PLANNING
        self.updated_at = datetime.now()
    
    def add_itinerary(self, itinerary: Itinerary):
        """Add a new itinerary version."""
        itinerary.version = len(self.itineraries) + 1
        self.itineraries.append(itinerary)
        self.updated_at = datetime.now()
    
    def get_current_itinerary(self) -> Optional[Itinerary]:
        """Get the latest itinerary version."""
        return self.itineraries[-1] if self.itineraries else None
    
    def get_form_summary(self) -> dict:
        """Get a summary of form status."""
        return {
            "filled_fields": self.form.get_filled_fields(),
            "missing_fields": self.form.get_missing_fields(),
            "is_complete": self.form.is_complete(),
            "is_locked": self.form_locked
        }


# In-memory session storage (would be replaced with database in production)
class SessionStore:
    """Simple in-memory session store."""
    
    def __init__(self):
        self._sessions: dict[str, Session] = {}
    
    def create(self) -> Session:
        """Create a new session."""
        session = Session()
        self._sessions[session.session_id] = session
        return session
    
    def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self._sessions.get(session_id)
    
    def update(self, session: Session):
        """Update a session."""
        self._sessions[session.session_id] = session
    
    def delete(self, session_id: str):
        """Delete a session."""
        self._sessions.pop(session_id, None)


# Global session store
session_store = SessionStore()
