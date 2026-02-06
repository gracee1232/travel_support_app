"""
Accuracy Monitor - Track LLM itinerary generation performance.
Monitors and logs metrics for continuous improvement.
"""
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ItineraryMetrics:
    """Metrics for a single itinerary generation."""
    session_id: str
    timestamp: str
    destination: str
    duration_days: int
    version: int
    
    # Accuracy metrics
    activities_count: int = 0
    activities_per_day_avg: float = 0.0
    time_slots_valid: int = 0
    time_slots_invalid: int = 0
    
    # Quality metrics
    has_meals: bool = False
    has_checkin: bool = False
    has_checkout: bool = False
    unique_locations: int = 0
    
    # Constraint adherence
    respects_daily_time: bool = True
    respects_pace: bool = True
    respects_duration: bool = True
    
    # User interaction
    modification_count: int = 0
    user_questions: int = 0
    
    # Scores
    accuracy_score: float = 0.0
    quality_score: float = 0.0
    constraint_score: float = 0.0
    overall_score: float = 0.0


class AccuracyMonitor:
    """
    Monitors and tracks LLM accuracy for itinerary generation.
    Logs metrics to file for analysis and model improvement.
    """
    
    def __init__(self, log_dir: str = "logs/accuracy"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.log_dir / "itinerary_metrics.jsonl"
        self.summary_file = self.log_dir / "accuracy_summary.json"
        self.current_sessions: Dict[str, ItineraryMetrics] = {}
    
    def start_session(self, session_id: str, form_data: Dict[str, Any]) -> None:
        """Initialize tracking for a new session."""
        destinations = form_data.get("destinations", [])
        destination = destinations[0] if destinations else "unknown"
        
        self.current_sessions[session_id] = ItineraryMetrics(
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            destination=destination,
            duration_days=form_data.get("trip_duration_days", 0),
            version=0
        )
    
    def _save_metrics(self, metrics: ItineraryMetrics) -> None:
        """Save metrics to file."""
        with open(self.metrics_file, "a") as f:
            f.write(json.dumps(asdict(metrics)) + "\n")
        
        self._update_summary(metrics)

    def evaluate_itinerary(
        self, 
        session_id: str, 
        itinerary: Dict[str, Any],
        form_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Evaluate an itinerary and compute accuracy metrics.
        """
        if session_id not in self.current_sessions:
            self.start_session(session_id, form_data)
        
        metrics = self.current_sessions[session_id]
        # Create a copy for this version so we don't overwrite history if we want to track sequence
        # For now, just logging the current state is fine, but strictly we might want new records per version.
        # Let's just log the snapshot.
        metrics.version = itinerary.get("version", 1)
        
        days = itinerary.get("days", [])
        
        # Count activities
        total_activities = 0
        time_valid = 0
        time_invalid = 0
        locations = set()
        has_meals = False
        has_checkin = False
        has_checkout = False
        
        for day in days:
            activities = day.get("activities", [])
            total_activities += len(activities)
            
            for act in activities:
                # Track locations
                location = act.get("location", "")
                if location:
                    locations.add(location)
                
                # Check activity types
                act_type = (act.get("type") or act.get("activity_type", "")).lower()
                if act_type == "meal":
                    has_meals = True
                elif act_type == "checkin":
                    has_checkin = True
                elif act_type == "checkout":
                    has_checkout = True
                
                # Validate time slots
                time_slot = act.get("time_slot") or act.get("time", "")
                if self._is_valid_time_slot(time_slot):
                    time_valid += 1
                else:
                    time_invalid += 1
        
        # Update metrics
        metrics.activities_count = total_activities
        metrics.activities_per_day_avg = total_activities / len(days) if days else 0
        metrics.time_slots_valid = time_valid
        metrics.time_slots_invalid = time_invalid
        metrics.has_meals = has_meals
        metrics.has_checkin = has_checkin
        metrics.has_checkout = has_checkout
        metrics.unique_locations = len(locations)
        
        # Check constraint adherence
        expected_days = form_data.get("trip_duration_days", 0)
        metrics.respects_duration = len(days) == expected_days
        
        pace = form_data.get("sightseeing_pace", "moderate")
        if pace == "relaxed":
            metrics.respects_pace = metrics.activities_per_day_avg <= 5
        elif pace == "packed":
            metrics.respects_pace = metrics.activities_per_day_avg >= 6
        else:
            metrics.respects_pace = 4 <= metrics.activities_per_day_avg <= 7
        
        # Calculate scores
        metrics.accuracy_score = self._calculate_accuracy_score(metrics)
        metrics.quality_score = self._calculate_quality_score(metrics)
        metrics.constraint_score = self._calculate_constraint_score(metrics)
        metrics.overall_score = (
            metrics.accuracy_score * 0.3 +
            metrics.quality_score * 0.4 +
            metrics.constraint_score * 0.3
        )
        
        # Save this evaluation
        self._save_metrics(metrics)
        
        return {
            "accuracy": metrics.accuracy_score,
            "quality": metrics.quality_score,
            "constraints": metrics.constraint_score,
            "overall": metrics.overall_score
        }
    
    def log_modification(self, session_id: str) -> None:
        """Track that a modification was made."""
        if session_id in self.current_sessions:
            self.current_sessions[session_id].modification_count += 1
    
    def log_question(self, session_id: str) -> None:
        """Track that a question was asked."""
        if session_id in self.current_sessions:
            self.current_sessions[session_id].user_questions += 1
    
    def finalize_session(self, session_id: str) -> Optional[ItineraryMetrics]:
        """
        Finalize and save session metrics.
        
        Args:
            session_id: Session to finalize
            
        Returns:
            Final metrics for the session
        """
        if session_id not in self.current_sessions:
            return None
        
        metrics = self.current_sessions.pop(session_id)
        
        # Append to metrics log
        with open(self.metrics_file, "a") as f:
            f.write(json.dumps(asdict(metrics)) + "\n")
        
        # Update summary
        self._update_summary(metrics)
        
        return metrics
    
    def get_summary(self) -> Dict[str, Any]:
        """Get accuracy summary statistics."""
        if not self.summary_file.exists():
            return {"total_sessions": 0, "average_scores": {}}
        
        with open(self.summary_file, "r") as f:
            return json.load(f)
    
    def get_recent_metrics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent session metrics."""
        if not self.metrics_file.exists():
            return []
        
        metrics = []
        with open(self.metrics_file, "r") as f:
            for line in f:
                try:
                    metrics.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        return metrics[-limit:]
    
    def _is_valid_time_slot(self, time_slot: str) -> bool:
        """Check if a time slot is valid (HH:MM - HH:MM format)."""
        if not time_slot or " - " not in time_slot:
            return False
        
        try:
            parts = time_slot.split(" - ")
            if len(parts) != 2:
                return False
            
            for part in parts:
                h, m = part.split(":")
                if not (0 <= int(h) <= 23 and 0 <= int(m) <= 59):
                    return False
            return True
        except (ValueError, IndexError):
            return False
    
    def _calculate_accuracy_score(self, metrics: ItineraryMetrics) -> float:
        """Calculate accuracy score based on format correctness."""
        score = 100.0
        
        # Penalize invalid time slots
        total_slots = metrics.time_slots_valid + metrics.time_slots_invalid
        if total_slots > 0:
            validity_rate = metrics.time_slots_valid / total_slots
            score *= validity_rate
        
        # Penalize missing activities
        if metrics.activities_count == 0:
            score *= 0.1
        elif metrics.activities_count < metrics.duration_days * 2:
            score *= 0.5
        
        return round(score, 2)
    
    def _calculate_quality_score(self, metrics: ItineraryMetrics) -> float:
        """Calculate quality score based on itinerary completeness."""
        score = 100.0
        
        # Check for essential components
        if not metrics.has_meals:
            score -= 15
        if metrics.duration_days > 0 and not metrics.has_checkin:
            score -= 10
        if metrics.duration_days > 0 and not metrics.has_checkout:
            score -= 10
        
        # Variety bonus
        if metrics.unique_locations >= metrics.duration_days * 3:
            score += 5
        
        # Activity balance
        if 4 <= metrics.activities_per_day_avg <= 7:
            score += 10
        
        return max(0, min(100, round(score, 2)))
    
    def _calculate_constraint_score(self, metrics: ItineraryMetrics) -> float:
        """Calculate score based on constraint adherence."""
        score = 100.0
        
        if not metrics.respects_duration:
            score -= 30
        if not metrics.respects_pace:
            score -= 20
        if not metrics.respects_daily_time:
            score -= 20
        
        return max(0, round(score, 2))
    
    def _update_summary(self, new_metrics: ItineraryMetrics) -> None:
        """Update the running summary with new metrics."""
        summary = self.get_summary() if self.summary_file.exists() else {
            "total_sessions": 0,
            "average_scores": {
                "accuracy": 0,
                "quality": 0,
                "constraints": 0,
                "overall": 0
            },
            "by_destination": {},
            "last_updated": None
        }
        
        n = summary["total_sessions"]
        avg = summary["average_scores"]
        
        # Update running averages
        summary["total_sessions"] = n + 1
        summary["average_scores"]["accuracy"] = round(
            (avg["accuracy"] * n + new_metrics.accuracy_score) / (n + 1), 2
        )
        summary["average_scores"]["quality"] = round(
            (avg["quality"] * n + new_metrics.quality_score) / (n + 1), 2
        )
        summary["average_scores"]["constraints"] = round(
            (avg["constraints"] * n + new_metrics.constraint_score) / (n + 1), 2
        )
        summary["average_scores"]["overall"] = round(
            (avg["overall"] * n + new_metrics.overall_score) / (n + 1), 2
        )
        
        # Track by destination
        dest = new_metrics.destination.lower()
        if dest not in summary["by_destination"]:
            summary["by_destination"][dest] = {
                "count": 0,
                "avg_score": 0
            }
        
        dest_data = summary["by_destination"][dest]
        dest_n = dest_data["count"]
        dest_data["count"] = dest_n + 1
        dest_data["avg_score"] = round(
            (dest_data["avg_score"] * dest_n + new_metrics.overall_score) / (dest_n + 1), 2
        )
        
        summary["last_updated"] = datetime.now().isoformat()
        
        with open(self.summary_file, "w") as f:
            json.dump(summary, f, indent=2)


# Global monitor instance
_monitor: Optional[AccuracyMonitor] = None


def get_accuracy_monitor() -> AccuracyMonitor:
    """Get or create the global accuracy monitor."""
    global _monitor
    if _monitor is None:
        _monitor = AccuracyMonitor()
    return _monitor
