import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def round_to_minute(dt: Optional[datetime] = None) -> datetime:
    """Round timestamp to the nearest minute to prevent fine-grained caller deanonymization."""
    target = dt or datetime.utcnow()
    return target.replace(second=0, microsecond=0)


class AnonymousSession(Base):
    """Anonymous helpline call record.
    
    STRICT PRIVACY GUARANTEES:
    - No telephone numbers or caller IDs.
    - No caller names, addresses, or personal identifiers.
    - No audio recordings or voice transcripts.
    - Timestamps are rounded to the minute.
    """

    __tablename__ = "anonymous_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    selected_language = Column(String(10), nullable=True)  # "en", "hi", "mr"
    symptom_category = Column(String(50), nullable=True, default="unspecified")
    urgency_category = Column(String(30), nullable=False, default="general_guidance")  # "emergency", "prompt_assessment", "general_guidance"
    referral_recommended = Column(Boolean, nullable=False, default=False)
    is_completed = Column(Boolean, nullable=False, default=False)
    duration_seconds = Column(Integer, nullable=False, default=0)
    turns_count = Column(Integer, nullable=False, default=0)
    is_synthetic = Column(Boolean, nullable=False, default=False)  # Clearly labels test/demo records
    created_at = Column(DateTime, nullable=False, default=round_to_minute)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "session_id": self.id,
            "selected_language": self.selected_language,
            "symptom_category": self.symptom_category,
            "urgency_category": self.urgency_category,
            "referral_recommended": self.referral_recommended,
            "is_completed": self.is_completed,
            "duration_seconds": self.duration_seconds,
            "turns_count": self.turns_count,
            "is_synthetic": self.is_synthetic,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
