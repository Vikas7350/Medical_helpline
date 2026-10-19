import csv
import io
import random
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session
from app.api.deps import AdminAuth, DatabaseSession
from app.api.v1.schemas import AnalyticsResponse, ReportItem, ReportsListResponse
from app.database.models import AnonymousSession, round_to_minute
from app.database.repository import SessionRepository

router = APIRouter(prefix="/admin", tags=["Admin Analytics & Reports"], dependencies=[AdminAuth])


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    start_date: Optional[datetime] = Query(None, description="ISO format start date"),
    end_date: Optional[datetime] = Query(None, description="ISO format end date"),
    include_synthetic: bool = Query(True, description="Include synthetic demo records in metrics"),
    only_synthetic: bool = Query(False, description="Filter for synthetic demo records only"),
    db: Session = DatabaseSession,
):
    """Return aggregated anonymous statistics with date and synthetic filtering."""
    analytics = SessionRepository.get_analytics(
        db=db,
        start_date=start_date,
        end_date=end_date,
        include_synthetic=include_synthetic,
        only_synthetic=only_synthetic,
    )
    return analytics


@router.get("/reports", response_model=ReportsListResponse)
async def get_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    urgency: Optional[str] = Query(None, description="emergency | prompt_assessment | general_guidance"),
    language: Optional[str] = Query(None, description="en | hi | mr"),
    include_synthetic: bool = Query(True),
    only_synthetic: bool = Query(False),
    db: Session = DatabaseSession,
):
    """Retrieve authorized anonymous report records."""
    items, total = SessionRepository.get_reports(
        db=db,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        urgency=urgency,
        language=language,
        include_synthetic=include_synthetic,
        only_synthetic=only_synthetic,
    )

    report_items = [
        ReportItem(
            session_id=item.id,
            selected_language=item.selected_language,
            symptom_category=item.symptom_category,
            urgency_category=item.urgency_category,
            referral_recommended=item.referral_recommended,
            is_completed=item.is_completed,
            duration_seconds=item.duration_seconds,
            turns_count=item.turns_count,
            is_synthetic=item.is_synthetic,
            created_at=item.created_at.isoformat() if item.created_at else None,
            completed_at=item.completed_at.isoformat() if item.completed_at else None,
        )
        for item in items
    ]

    return ReportsListResponse(
        total=total,
        skip=skip,
        limit=limit,
        items=report_items,
    )


@router.get("/reports/export")
async def export_reports_csv(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    urgency: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    include_synthetic: bool = Query(True),
    only_synthetic: bool = Query(False),
    db: Session = DatabaseSession,
):
    """Export anonymous reports in CSV format for health district planning."""
    items, _ = SessionRepository.get_reports(
        db=db,
        skip=0,
        limit=5000,
        start_date=start_date,
        end_date=end_date,
        urgency=urgency,
        language=language,
        include_synthetic=include_synthetic,
        only_synthetic=only_synthetic,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "session_id",
        "selected_language",
        "symptom_category",
        "urgency_category",
        "referral_recommended",
        "is_completed",
        "duration_seconds",
        "turns_count",
        "is_synthetic",
        "created_at",
        "completed_at",
    ])

    for item in items:
        writer.writerow([
            item.id,
            item.selected_language or "unknown",
            item.symptom_category or "unspecified",
            item.urgency_category,
            item.referral_recommended,
            item.is_completed,
            item.duration_seconds,
            item.turns_count,
            item.is_synthetic,
            item.created_at.isoformat() if item.created_at else "",
            item.completed_at.isoformat() if item.completed_at else "",
        ])

    csv_data = output.getvalue()
    filename = f"helpline_anonymous_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/seed-demo", status_code=status.HTTP_201_CREATED)
async def seed_demo_data(
    count: int = Query(50, ge=5, le=500, description="Number of synthetic records to seed"),
    db: Session = DatabaseSession,
):
    """Seed synthetic demographic data for testing and hackathon demonstration."""
    languages = ["hi", "mr", "en"]
    lang_weights = [0.55, 0.35, 0.10]  # Realistic rural distribution

    symptom_categories = [
        ("fever_infection", "prompt_assessment", True),
        ("gastrointestinal", "prompt_assessment", True),
        ("respiratory_mild", "general_guidance", False),
        ("cardiovascular", "emergency", True),
        ("respiratory", "emergency", True),
        ("musculoskeletal_mild", "general_guidance", False),
        ("animal_bite_wound", "prompt_assessment", True),
        ("maternal_health", "prompt_assessment", True),
    ]

    now = datetime.utcnow()
    created_sessions = []

    for _ in range(count):
        lang = random.choices(languages, weights=lang_weights, k=1)[0]
        cat, urg, ref = random.choice(symptom_categories)
        days_ago = random.randint(0, 14)
        hours_ago = random.randint(0, 23)
        created_dt = round_to_minute(now - timedelta(days=days_ago, hours=hours_ago))
        duration = random.randint(60, 360)
        is_completed = random.random() > 0.12  # 88% completion rate

        session = AnonymousSession(
            selected_language=lang,
            symptom_category=cat,
            urgency_category=urg,
            referral_recommended=ref,
            is_completed=is_completed,
            duration_seconds=duration,
            turns_count=random.randint(3, 7),
            is_synthetic=True,
            created_at=created_dt,
            completed_at=created_dt + timedelta(seconds=duration) if is_completed else None,
        )
        db.add(session)
        created_sessions.append(session)

    db.commit()

    return {
        "status": "success",
        "message": f"Successfully generated {count} labeled synthetic records for demonstration.",
        "records_seeded": count,
    }
