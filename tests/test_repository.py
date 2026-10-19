from datetime import datetime, timedelta
from app.database.models import AnonymousSession, round_to_minute
from app.database.repository import SessionRepository


def test_repository_privacy_timestamp_rounding(db_session):
    exact_time = datetime(2026, 10, 16, 14, 32, 45, 123456)
    rounded = round_to_minute(exact_time)
    assert rounded.second == 0
    assert rounded.microsecond == 0
    assert rounded.minute == 32
    assert rounded.hour == 14


def test_repository_crud_and_privacy(db_session):
    # Create session
    session = SessionRepository.create_session(
        db=db_session,
        session_id="test-privacy-uuid-001",
        language="hi",
        is_synthetic=True,
    )
    assert session.id == "test-privacy-uuid-001"
    assert session.selected_language == "hi"
    assert session.is_synthetic is True

    # Update with triage findings
    updated = SessionRepository.update_session(
        db=db_session,
        session_id="test-privacy-uuid-001",
        symptom_category="fever_infection",
        urgency_category="prompt_assessment",
        referral_recommended=True,
        is_completed=True,
    )
    assert updated.symptom_category == "fever_infection"
    assert updated.urgency_category == "prompt_assessment"
    assert updated.referral_recommended is True


def test_repository_data_retention_purge(db_session):
    # Insert an old session older than 90 days
    old_date = datetime.utcnow() - timedelta(days=95)
    old_session = AnonymousSession(
        id="old-session-expired",
        selected_language="mr",
        created_at=old_date,
    )
    # Insert a fresh session
    fresh_session = AnonymousSession(
        id="fresh-session-active",
        selected_language="en",
        created_at=datetime.utcnow(),
    )
    db_session.add(old_session)
    db_session.add(fresh_session)
    db_session.commit()

    # Run retention cleanup for 90 days
    purged = SessionRepository.cleanup_old_records(db=db_session, retention_days=90)
    assert purged >= 1

    # Verify old session was deleted and fresh session remains
    assert SessionRepository.get_by_id(db_session, "old-session-expired") is None
    assert SessionRepository.get_by_id(db_session, "fresh-session-active") is not None
