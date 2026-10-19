"""Script to seed realistic synthetic demo data into the Helpline database."""

import os
import random
import sys
from datetime import datetime, timedelta

# Add workspace to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.models import AnonymousSession, round_to_minute
from app.database.session import SessionLocal, init_db


def seed_synthetic_data(count: int = 100):
    init_db()
    db = SessionLocal()

    languages = ["hi", "mr", "en"]
    lang_weights = [0.55, 0.35, 0.10]

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
    print(f"Seeding {count} synthetic anonymous records...")

    for _ in range(count):
        lang = random.choices(languages, weights=lang_weights, k=1)[0]
        cat, urg, ref = random.choice(symptom_categories)
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        created_dt = round_to_minute(now - timedelta(days=days_ago, hours=hours_ago))
        duration = random.randint(45, 420)
        is_completed = random.random() > 0.10

        session = AnonymousSession(
            selected_language=lang,
            symptom_category=cat,
            urgency_category=urg,
            referral_recommended=ref,
            is_completed=is_completed,
            duration_seconds=duration,
            turns_count=random.randint(2, 6),
            is_synthetic=True,
            created_at=created_dt,
            completed_at=created_dt + timedelta(seconds=duration) if is_completed else None,
        )
        db.add(session)

    db.commit()
    total = db.query(AnonymousSession).count()
    synthetic_count = db.query(AnonymousSession).filter(AnonymousSession.is_synthetic == True).count()
    db.close()

    print(f"Successfully seeded {count} demo records.")
    print(f"Total records in DB: {total} ({synthetic_count} labeled synthetic).")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    seed_synthetic_data(count)
