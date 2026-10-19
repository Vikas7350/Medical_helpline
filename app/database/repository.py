from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.database.models import AnonymousSession, round_to_minute


class SessionRepository:
    """Repository handling all database operations with privacy guarantees."""

    @staticmethod
    def create_session(
        db: Session,
        session_id: Optional[str] = None,
        language: Optional[str] = None,
        is_synthetic: bool = False,
    ) -> AnonymousSession:
        session = AnonymousSession(
            id=session_id,
            selected_language=language,
            is_synthetic=is_synthetic,
            created_at=round_to_minute(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_by_id(db: Session, session_id: str) -> Optional[AnonymousSession]:
        return db.query(AnonymousSession).filter(AnonymousSession.id == session_id).first()

    @staticmethod
    def update_session(
        db: Session,
        session_id: str,
        **updates: Any,
    ) -> Optional[AnonymousSession]:
        session = db.query(AnonymousSession).filter(AnonymousSession.id == session_id).first()
        if not session:
            return None

        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)

        db.commit()
        db.refresh(session)
        return session

    @staticmethod
    def get_analytics(
        db: Session,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_synthetic: bool = True,
        only_synthetic: bool = False,
    ) -> Dict[str, Any]:
        """Aggregate anonymous statistics across interactions with date and synthetic filtering."""
        query = db.query(AnonymousSession)

        if only_synthetic:
            query = query.filter(AnonymousSession.is_synthetic == True)
        elif not include_synthetic:
            query = query.filter(AnonymousSession.is_synthetic == False)

        if start_date:
            query = query.filter(AnonymousSession.created_at >= start_date)
        if end_date:
            query = query.filter(AnonymousSession.created_at <= end_date)

        total_interactions = query.count()

        if total_interactions == 0:
            return {
                "total_interactions": 0,
                "languages": {},
                "symptom_categories": {},
                "urgency_distribution": {
                    "emergency": 0,
                    "prompt_assessment": 0,
                    "general_guidance": 0,
                },
                "referrals": {
                    "recommended_count": 0,
                    "percentage": 0.0,
                },
                "completion": {
                    "completed_count": 0,
                    "incomplete_count": 0,
                    "completion_rate_percentage": 0.0,
                },
                "synthetic_records_count": 0,
                "live_records_count": 0,
            }

        # Language breakdown
        lang_counts = (
            query.with_entities(AnonymousSession.selected_language, func.count(AnonymousSession.id))
            .group_by(AnonymousSession.selected_language)
            .all()
        )
        languages = {lang or "unselected": count for lang, count in lang_counts}

        # Symptom category breakdown
        symptom_counts = (
            query.with_entities(AnonymousSession.symptom_category, func.count(AnonymousSession.id))
            .group_by(AnonymousSession.symptom_category)
            .order_by(func.count(AnonymousSession.id).desc())
            .all()
        )
        symptom_categories = {sym or "unspecified": count for sym, count in symptom_counts}

        # Urgency breakdown
        urgency_counts = (
            query.with_entities(AnonymousSession.urgency_category, func.count(AnonymousSession.id))
            .group_by(AnonymousSession.urgency_category)
            .all()
        )
        urgency_distribution = {
            "emergency": 0,
            "prompt_assessment": 0,
            "general_guidance": 0,
        }
        for urg, count in urgency_counts:
            if urg in urgency_distribution:
                urgency_distribution[urg] = count

        # Referral stats
        referral_count = query.filter(AnonymousSession.referral_recommended == True).count()
        referral_percentage = round((referral_count / total_interactions) * 100, 1)

        # Completion stats
        completed_count = query.filter(AnonymousSession.is_completed == True).count()
        incomplete_count = total_interactions - completed_count
        completion_rate = round((completed_count / total_interactions) * 100, 1)

        # Synthetic vs Live count
        synthetic_count = query.filter(AnonymousSession.is_synthetic == True).count()
        live_count = total_interactions - synthetic_count

        return {
            "total_interactions": total_interactions,
            "languages": languages,
            "symptom_categories": symptom_categories,
            "urgency_distribution": urgency_distribution,
            "referrals": {
                "recommended_count": referral_count,
                "percentage": referral_percentage,
            },
            "completion": {
                "completed_count": completed_count,
                "incomplete_count": incomplete_count,
                "completion_rate_percentage": completion_rate,
            },
            "synthetic_records_count": synthetic_count,
            "live_records_count": live_count,
        }

    @staticmethod
    def get_reports(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        urgency: Optional[str] = None,
        language: Optional[str] = None,
        include_synthetic: bool = True,
        only_synthetic: bool = False,
    ) -> Tuple[List[AnonymousSession], int]:
        """Fetch filtered anonymous report items for admin table or export."""
        query = db.query(AnonymousSession)

        if only_synthetic:
            query = query.filter(AnonymousSession.is_synthetic == True)
        elif not include_synthetic:
            query = query.filter(AnonymousSession.is_synthetic == False)

        if start_date:
            query = query.filter(AnonymousSession.created_at >= start_date)
        if end_date:
            query = query.filter(AnonymousSession.created_at <= end_date)
        if urgency:
            query = query.filter(AnonymousSession.urgency_category == urgency)
        if language:
            query = query.filter(AnonymousSession.selected_language == language)

        total_count = query.count()
        items = query.order_by(AnonymousSession.created_at.desc()).offset(skip).limit(limit).all()
        return items, total_count

    @staticmethod
    def cleanup_old_records(db: Session, retention_days: int) -> int:
        """Purge records older than retention_days for privacy compliance."""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        deleted = db.query(AnonymousSession).filter(AnonymousSession.created_at < cutoff_date).delete()
        db.commit()
        logger.info(f"Purged {deleted} anonymous sessions older than {retention_days} days.")
        return deleted
