from app.triage.engine import TriageEngine


def test_emergency_red_flag_chest_pain_bypass(client):
    """Potential emergency warning signs must trigger immediate emergency-care advice without delay."""
    # Create session
    create_res = client.post("/api/v1/sessions", json={})
    sid = create_res.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid}/language", json={"language": "1"})

    # Caller reports severe chest pain
    turn = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "I have severe chest pain and left arm numbness"})
    assert turn.status_code == 200
    data = turn.json()

    # Must jump directly to GUIDANCE_DELIVERED with EMERGENCY tier
    assert data["state"] == "GUIDANCE_DELIVERED"
    assert data["triage"]["urgency_category"] == "emergency"
    assert data["triage"]["is_emergency"] is True
    assert data["triage"]["referral_recommended"] is True
    assert "108" in data["spoken_text"]


def test_emergency_red_flag_hindi(client):
    create_res = client.post("/api/v1/sessions", json={})
    sid = create_res.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid}/language", json={"language": "2"})

    turn = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "सीने में बहुत तेज दर्द है और दम घुट रहा है"})
    assert turn.status_code == 200
    data = turn.json()

    assert data["triage"]["urgency_category"] == "emergency"
    assert "108" in data["spoken_text"]
    assert "आपातकालीन" in data["spoken_text"]


def test_emergency_red_flag_marathi(client):
    create_res = client.post("/api/v1/sessions", json={})
    sid = create_res.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid}/language", json={"language": "3"})

    turn = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "छातीत तीव्र वेदना होत आहेत आणि श्वास कोंडला आहे"})
    assert turn.status_code == 200
    data = turn.json()

    assert data["triage"]["urgency_category"] == "emergency"
    assert "१०८" in data["spoken_text"] or "108" in data["spoken_text"]
    assert "तातडीची" in data["spoken_text"]


def test_ambiguous_symptoms_never_declares_safe():
    """Unclear symptoms must default to professional assessment and never declare the caller safe."""
    assessment = TriageEngine.evaluate("feeling a bit strange and weird today", language="en")
    assert assessment.urgency_category == "prompt_assessment"
    assert assessment.referral_recommended is True
    assert "safe" not in assessment.guidance_text.lower()
    assert "Primary Health Centre" in assessment.guidance_text or "consult" in assessment.guidance_text


def test_safety_guardrails_blocks_prescriptions():
    """AI must not prescribe medication or dosage."""
    unsafe_text = "You should take Paracetamol 500mg twice daily for fever."
    safe_text = TriageEngine.validate_safety_guardrails(unsafe_text, fallback_lang="en")
    assert "500mg" not in safe_text
    assert "consult a registered doctor" in safe_text.lower()


def test_safety_guardrails_blocks_false_safety():
    """AI must not declare a caller completely safe."""
    unsafe_text = "You are completely safe and nothing to worry about."
    safe_text = TriageEngine.validate_safety_guardrails(unsafe_text, fallback_lang="en")
    assert "completely safe" not in safe_text
