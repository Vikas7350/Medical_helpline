def test_full_conversation_flow(client):
    # 1. Create session
    create_res = client.post("/api/v1/sessions", json={})
    sid = create_res.json()["session_id"]

    # 2. Select Hindi ('2')
    lang_res = client.post(f"/api/v1/sessions/{sid}/language", json={"language": "2"})
    assert lang_res.json()["state"] == "SYMPTOM_INPUT"

    # 3. Provide non-emergency symptoms
    turn1 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "हल्की सर्दी और जुकाम है"})
    assert turn1.status_code == 200
    assert turn1.json()["state"] == "DURATION_INPUT"
    assert "कितने दिनों से है" in turn1.json()["spoken_text"]

    # 4. Provide duration (< 3 days = '1')
    turn2 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "1", "is_dtmf": True})
    assert turn2.status_code == 200
    assert turn2.json()["state"] == "SEVERITY_INPUT"
    assert "तकलीफ कितनी है" in turn2.json()["spoken_text"]

    # 5. Provide severity (mild = '1')
    turn3 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "1", "is_dtmf": True})
    assert turn3.status_code == 200
    assert turn3.json()["state"] == "GUIDANCE_DELIVERED"
    assert turn3.json()["is_completed"] is True
    assert turn3.json()["triage"]["urgency_category"] == "general_guidance"


def test_repeat_prompt_digit_zero(client):
    create_res = client.post("/api/v1/sessions", json={})
    sid = create_res.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid}/language", json={"language": "1"})

    # Caller presses 0 to repeat
    repeat_res = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "0", "is_dtmf": True})
    assert repeat_res.status_code == 200
    assert "repeat this information" in repeat_res.json()["spoken_text"]
    assert repeat_res.json()["state"] == "SYMPTOM_INPUT"


def test_end_call_digit_nine(client):
    create_res = client.post("/api/v1/sessions", json={})
    sid = create_res.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid}/language", json={"language": "1"})

    # Caller presses 9 to end
    end_res = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "9", "is_dtmf": True})
    assert end_res.status_code == 200
    assert end_res.json()["state"] == "COMPLETED"
    assert end_res.json()["should_hangup"] is True
    assert "Goodbye" in end_res.json()["spoken_text"]


def test_silence_and_max_retries(client):
    create_res = client.post("/api/v1/sessions", json={})
    sid = create_res.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid}/language", json={"language": "1"})

    # Empty turn 1: Silence prompt
    t1 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": ""})
    assert t1.status_code == 200
    assert "did not hear anything" in t1.json()["spoken_text"]
    assert t1.json()["should_hangup"] is False

    # Empty turn 2
    t2 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": ""})
    assert t2.status_code == 200
    assert t2.json()["should_hangup"] is False

    # Empty turn 3: Max retry exceeded -> safe referral and hangup
    t3 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": ""})
    assert t3.status_code == 200
    assert t3.json()["should_hangup"] is True
    assert "having trouble hearing you" in t3.json()["spoken_text"]
