from app.core.config import settings


def test_admin_auth_required(client):
    # Without auth header
    unauth_res = client.get("/api/v1/admin/analytics")
    assert unauth_res.status_code == 401

    # With invalid key
    bad_res = client.get("/api/v1/admin/analytics", headers={"X-Admin-API-Key": "wrong-key"})
    assert bad_res.status_code == 401

    # With valid API key
    valid_res = client.get("/api/v1/admin/analytics", headers={"X-Admin-API-Key": settings.ADMIN_API_KEY})
    assert valid_res.status_code == 200

    # With valid Bearer token
    bearer_res = client.get("/api/v1/admin/analytics", headers={"Authorization": f"Bearer {settings.ADMIN_SECRET_TOKEN}"})
    assert bearer_res.status_code == 200


def test_analytics_metrics_calculation(client, admin_headers):
    # Seed 20 demo records
    seed_res = client.post("/api/v1/admin/seed-demo?count=20", headers=admin_headers)
    assert seed_res.status_code == 201

    # Fetch analytics
    res = client.get("/api/v1/admin/analytics", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_interactions"] >= 20
    assert "hi" in data["languages"] or "en" in data["languages"] or "mr" in data["languages"]
    assert "emergency" in data["urgency_distribution"]
    assert "prompt_assessment" in data["urgency_distribution"]
    assert "recommended_count" in data["referrals"]
    assert "completion_rate_percentage" in data["completion"]
    assert data["synthetic_records_count"] >= 20


def test_reports_pagination_and_csv_export(client, admin_headers):
    # Seed 10 records
    client.post("/api/v1/admin/seed-demo?count=10", headers=admin_headers)

    # 1. Fetch paginated reports
    reports_res = client.get("/api/v1/admin/reports?skip=0&limit=5", headers=admin_headers)
    assert reports_res.status_code == 200
    data = reports_res.json()
    assert data["total"] >= 10
    assert len(data["items"]) == 5

    # Check that privacy fields are respected (no caller phone or name in fields)
    sample = data["items"][0]
    assert "session_id" in sample
    assert "caller_phone" not in sample
    assert "caller_name" not in sample
    assert "transcript" not in sample

    # 2. Export CSV
    csv_res = client.get("/api/v1/admin/reports/export", headers=admin_headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "attachment" in csv_res.headers["content-disposition"]
    csv_text = csv_res.text
    assert "session_id,selected_language,symptom_category" in csv_text
