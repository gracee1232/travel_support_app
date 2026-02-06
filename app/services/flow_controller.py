"""
Flow Controller - Backend conversation flow management.
Decides when to extract, plan, and what questions to ask.
"""
from typing import Optional, Tuple
from enum import Enum

from .extractor import get_extractor
from .planner import get_planner
from .accuracy_monitor import get_accuracy_monitor
from ..models.session import Session, SessionState, session_store
from ..models.form_schema import FIELD_QUESTIONS, TravelForm


class ResponseType(str, Enum):
    """Type of response from flow controller."""
    QUESTION = "question"  # Asking for missing info
    CONFIRMATION = "confirmation"  # Confirming extracted data
    READY_TO_PLAN = "ready_to_plan"  # Form complete, ready to generate
    ITINERARY = "itinerary"  # Returning generated itinerary
    MODIFICATION = "modification"  # Itinerary modification result
    ERROR = "error"  # Error message


class FlowController:
    """
    Controls the conversation flow.
    
    The backend (this class) makes all decisions:
    - When to call the extractor
    - When to call the planner
    - What questions to ask
    - When the form is complete
    """
    
    def __init__(self):
        self.extractor = get_extractor()
        self.planner = get_planner()
    
    async def process_message(
        self,
        session: Session,
        user_message: str
    ) -> Tuple[ResponseType, str, Optional[dict]]:
        """
        Process a user message and return appropriate response.
        
        In Form-First architecture:
        - If form is locked, chat only handles preferences and itinerary generation
        - Form fields are NOT extracted from chat (form is the primary input)
        
        Args:
            session: Current user session
            user_message: The user's message
            
        Returns:
            Tuple of (response_type, message, optional_data)
        """
        # Add user message to history
        session.add_message("user", user_message)
        
        # FORM-FIRST: If form is locked, skip COLLECTING and go to preferences/planning
        if session.form_locked:
            # Form is locked via form submission, treat as FORM_COMPLETE
            if session.state == SessionState.COLLECTING:
                session.state = SessionState.FORM_COMPLETE
                session_store.update(session)
            
            if session.state == SessionState.FORM_COMPLETE:
                return await self._handle_form_complete(session, user_message)
            elif session.state in (SessionState.PLANNING, SessionState.ITERATING, SessionState.COMPLETE):
                return await self._handle_post_planning(session, user_message)
        
        # Handle based on current state (legacy chat-first flow)
        if session.state == SessionState.COLLECTING:
            return await self._handle_collecting(session, user_message)
        
        elif session.state == SessionState.FORM_COMPLETE:
            return await self._handle_form_complete(session, user_message)
        
        elif session.state in (SessionState.PLANNING, SessionState.ITERATING, SessionState.COMPLETE):
            return await self._handle_post_planning(session, user_message)
        
        return ResponseType.ERROR, "Unknown session state", None
    
    async def _handle_collecting(
        self,
        session: Session,
        user_message: str
    ) -> Tuple[ResponseType, str, Optional[dict]]:
        """Handle message during form collection phase."""
        
        # Extract information from message
        extracted = await self.extractor.extract(user_message, session.form)
        
        # Separate soft preferences from form fields
        soft_prefs = extracted.pop("soft_preferences", [])
        for pref in soft_prefs:
            session.add_soft_preference(pref)
        
        # Update form with extracted data
        if extracted:
            session.update_form(extracted)
        
        # Save session
        session_store.update(session)
        
        # Check if form is complete
        if session.form.is_complete():
            session.state = SessionState.FORM_COMPLETE
            session_store.update(session)
            
            response = self._generate_form_summary(session.form)
            response += "\n\n✅ **All information collected!** Would you like me to generate your itinerary?"
            
            session.add_message("assistant", response)
            return ResponseType.READY_TO_PLAN, response, session.get_form_summary()
        
        # Ask for missing fields
        missing = session.form.get_missing_fields()
        question = self._generate_question(missing, extracted)
        
        session.add_message("assistant", question)
        return ResponseType.QUESTION, question, {"missing_fields": missing}
    
    async def _handle_form_complete(
        self,
        session: Session,
        user_message: str
    ) -> Tuple[ResponseType, str, Optional[dict]]:
        """Handle message when form is complete but itinerary not yet generated."""
        
        # Check if user wants to generate
        lower_msg = user_message.lower()
        generate_keywords = ["yes", "generate", "plan", "create", "go ahead", "sure", "okay", "ok"]
        
        if any(kw in lower_msg for kw in generate_keywords):
            # Lock form and generate itinerary
            session.lock_form()
            session.state = SessionState.PLANNING
            
            # Generate itinerary
            itinerary = await self.planner.generate(
                session.form,
                session.soft_preferences
            )
            session.add_itinerary(itinerary)
            session.state = SessionState.COMPLETE
            session_store.update(session)
            
            # Monitor accuracy
            try:
                monitor = get_accuracy_monitor()
                scores = monitor.evaluate_itinerary(
                    session.session_id, 
                    itinerary.to_display_dict(), 
                    session.form.model_dump()
                )
                print(f"Itinerary accuracy scores: {scores}")
            except Exception as e:
                print(f"Monitoring error: {e}")
            
            response = "🎉 **Your itinerary is ready!**\n\n"
            response += self._format_itinerary_summary(itinerary)
            response += "\n\nWould you like me to make any changes?"
            
            session.add_message("assistant", response)
            return ResponseType.ITINERARY, response, itinerary.to_display_dict()
        
        # User might want to modify form before generating
        # Try to extract any new information
        extracted = await self.extractor.extract(user_message, session.form)
        soft_prefs = extracted.pop("soft_preferences", [])
        for pref in soft_prefs:
            session.add_soft_preference(pref)
        
        if soft_prefs:
            response = f"📝 Noted your preferences: {', '.join(soft_prefs)}\n\n"
            response += "Ready to generate your itinerary. Just say 'yes' or 'generate'!"
            session.add_message("assistant", response)
            session_store.update(session)
            return ResponseType.CONFIRMATION, response, None
        
        response = "Your travel information is complete! Say 'generate' or 'yes' to create your itinerary."
        session.add_message("assistant", response)
        return ResponseType.CONFIRMATION, response, None
    
    async def _handle_post_planning(
        self,
        session: Session,
        user_message: str
    ) -> Tuple[ResponseType, str, Optional[dict]]:
        """Handle message after itinerary is generated (modifications or questions)."""
        
        current_itinerary = session.get_current_itinerary()
        if not current_itinerary:
            return ResponseType.ERROR, "No itinerary found. Please start over.", None
            
        monitor = get_accuracy_monitor()
        
        # Check if this is likely a Q&A request vs a Modification request
        question_triggers = ["what", "how", "where", "when", "is ", "are ", "can ", "does ", "best ", "famous", "top", "recommend", "suggest", "tell", "info", "popular", "worth"]
        is_question = any(q in user_message.lower() for q in question_triggers)
        # "instead" should only be a mod trigger if it's not a question or if it looks like a resource swap
        mod_triggers = ["change", "add", "remove", "replace", "delete", "move", "swap", "update", "modify", "put", "use "]
        has_mod_intent = any(m in user_message.lower() for m in mod_triggers)
        
        # Special case for "instead" - if it's a question about another city, it's QA
        if "instead" in user_message.lower() and not has_mod_intent:
            has_mod_intent = False
        elif "instead" in user_message.lower():
            has_mod_intent = True
        
        # If it looks like a question AND doesn't have clear mod intent, or it's just a general query
        if (is_question and not has_mod_intent) or (not has_mod_intent and "?" in user_message):
            # This is likely a question about the trip, not a modification
            monitor.log_question(session.session_id)
            
            dest_str = ", ".join(session.form.destinations) if session.form.destinations else "your destination"
            answer = await self.planner.answer_question(current_itinerary, user_message, destination=dest_str)
            session.add_message("assistant", answer)
            
            # Return as QUESTION response type
            return ResponseType.QUESTION, answer, current_itinerary.to_display_dict()

        # Check for soft preferences and potential field updates
        extracted = await self.extractor.extract(user_message, session.form)
        
        # If extractor found NO field updates and we didn't detect mod intent, 
        # it might still be a question even if it didn't hit triggers (e.g., "famous food")
        has_hard_updates = any(v is not None for k, v in extracted.items() if k != "soft_preferences")
        
        if not has_mod_intent and not has_hard_updates:
            # Fallback for short queries without clear modification keywords
            monitor.log_question(session.session_id)
            answer = await self.planner.answer_question(current_itinerary, user_message)
            session.add_message("assistant", answer)
            return ResponseType.QUESTION, answer, current_itinerary.to_display_dict()
        soft_prefs = extracted.pop("soft_preferences", [])
        for pref in soft_prefs:
            session.add_soft_preference(pref)
        
        # Generate modified itinerary
        session.state = SessionState.ITERATING
        new_itinerary = await self.planner.modify(
            current_itinerary,
            session.form,
            user_message,
            session.soft_preferences
        )
        
        # Check if it was actually modified
        if new_itinerary.version > current_itinerary.version:
            monitor.log_modification(session.session_id)
            
            # Evaluate new itinerary
            try:
                scores = monitor.evaluate_itinerary(
                    session.session_id, 
                    new_itinerary.to_display_dict(), 
                    session.form.model_dump()
                )
                print(f"Modified itinerary accuracy scores: {scores}")
            except Exception as e:
                print(f"Monitoring error: {e}")
                
            session.add_itinerary(new_itinerary)
            session.state = SessionState.COMPLETE
            session_store.update(session)
            
            response = f"🔄 **Itinerary updated (Version {new_itinerary.version})!**\n\n"
            
            # Show what changed
            if new_itinerary.change_summary:
                response += f"{new_itinerary.change_summary}\n\n"
            elif new_itinerary.changes_made:
                response += "**Changes Made:**\n"
                for change in new_itinerary.changes_made:
                    response += f"• {change}\n"
                response += "\n"
            
            response += self._format_itinerary_summary(new_itinerary)
            response += "\n\nWould you like any other changes?"
            
            session.add_message("assistant", response)
            return ResponseType.MODIFICATION, response, new_itinerary.to_display_dict()
        else:
            # No change made - treat as QA response or simple acknowledgement
            # The planner might return same version if it couldn't modify
            monitor.log_question(session.session_id)
            
            response = new_itinerary.change_summary or "I couldn't verify that change given the constraints. Could you rephrase?"
            if not new_itinerary.change_summary:
                # Fallback response for simple chat/QA if planner didn't modify
                response = f"I can help with that! {user_message} is a great topic. (Simulated answer)"
            
            session.add_message("assistant", response)
            return ResponseType.QUESTION, response, current_itinerary.to_display_dict()
    
    def _generate_question(self, missing: list[str], just_extracted: dict) -> str:
        """Generate a natural question for missing fields."""
        # Acknowledge what was extracted
        parts = []
        
        if just_extracted:
            ack_items = []
            for field, value in just_extracted.items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                ack_items.append(f"**{field.replace('_', ' ').title()}**: {value}")
            
            if ack_items:
                parts.append("✓ Got it! " + ", ".join(ack_items[:3]))
        
        # Ask about missing fields (prioritize important ones first)
        priority_fields = [
            "destinations", "trip_duration_days", "start_date", "end_date",
            "traveler_count", "group_type", "daily_start_time", "daily_end_time",
            "sightseeing_pace", "travel_mode"
        ]
        
        # Find next field to ask about
        next_field = None
        for field in priority_fields:
            if field in missing:
                next_field = field
                break
        
        if not next_field and missing:
            next_field = missing[0]
        
        if next_field:
            question = FIELD_QUESTIONS.get(next_field, f"Please provide {next_field.replace('_', ' ')}")
            parts.append(f"\n\n❓ {question}")
        
        # Show progress
        total = 18  # Total mandatory fields
        filled = total - len(missing)
        parts.append(f"\n\n📊 Progress: {filled}/{total} fields complete")
        
        return "".join(parts)
    
    def _generate_form_summary(self, form: TravelForm) -> str:
        """Generate a summary of the completed form."""
        filled = form.get_filled_fields()
        
        lines = ["📋 **Your Trip Details:**"]
        
        key_fields = [
            ("destinations", "📍 Destinations"),
            ("trip_duration_days", "📅 Duration"),
            ("start_date", "🗓️ Start Date"),
            ("end_date", "🗓️ End Date"),
            ("traveler_count", "👥 Travelers"),
            ("group_type", "👨‍👩‍👧 Group Type"),
            ("sightseeing_pace", "🚶 Pace"),
            ("travel_mode", "🚗 Travel Mode"),
        ]
        
        for field, label in key_fields:
            if field in filled:
                value = filled[field]
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                lines.append(f"- {label}: {value}")
        
        return "\n".join(lines)
    
    def _format_itinerary_summary(self, itinerary) -> str:
        """Format itinerary for display."""
        lines = [f"**{itinerary.summary}**\n"]
        lines.append(f"📅 {len(itinerary.days)} days | 🚗 {itinerary.get_total_distance():.1f} km total\n")
        
        for day in itinerary.days:
            lines.append(f"\n**Day {day.day_number}** - {day.theme or day.date}")
            for act in day.activities[:4]:  # Show first 4 activities
                lines.append(f"  • {act.time_slot}: {act.location}")
            if len(day.activities) > 4:
                lines.append(f"  ... and {len(day.activities) - 4} more activities")
        
        return "\n".join(lines)


# Global flow controller
flow_controller: Optional[FlowController] = None


def get_flow_controller() -> FlowController:
    """Get or create the global flow controller."""
    global flow_controller
    if flow_controller is None:
        flow_controller = FlowController()
    return flow_controller
