def test_create_session(client):
    response = client.post("/api/v1/sessions", json={"is_synthetic": False})
    assert response.status_code == 201
    data = response.json()
    assert "session_id" in data
    assert data["state"] == "LANGUAGE_SELECT"
    assert "English" in data["spoken_text"]
    assert "हिंदी" in data["spoken_text"]
    assert "मराठी" in data["spoken_text"]


def test_select_language_digits(client):
    # Test English selection via '1'
    res1 = client.post("/api/v1/sessions", json={})
    sid1 = res1.json()["session_id"]
    lang1_res = client.post(f"/api/v1/sessions/{sid1}/language", json={"language": "1"})
    assert lang1_res.status_code == 200
    assert lang1_res.json()["language"] == "en"
    assert lang1_res.json()["state"] == "SYMPTOM_INPUT"

    # Test Hindi selection via '2'
    res2 = client.post("/api/v1/sessions", json={})
    sid2 = res2.json()["session_id"]
    lang2_res = client.post(f"/api/v1/sessions/{sid2}/language", json={"language": "2"})
    assert lang2_res.status_code == 200
    assert lang2_res.json()["language"] == "hi"
    assert lang2_res.json()["state"] == "SYMPTOM_INPUT"
    assert "हिंदी" in lang2_res.json()["spoken_text"]

    # Test Marathi selection via '3'
    res3 = client.post("/api/v1/sessions", json={})
    sid3 = res3.json()["session_id"]
    lang3_res = client.post(f"/api/v1/sessions/{sid3}/language", json={"language": "3"})
    assert lang3_res.status_code == 200
    assert lang3_res.json()["language"] == "mr"
    assert lang3_res.json()["state"] == "SYMPTOM_INPUT"
    assert "मराठी" in lang3_res.json()["spoken_text"]


def test_invalid_language_selection(client):
    res = client.post("/api/v1/sessions", json={})
    sid = res.json()["session_id"]

    # Pressing invalid digit '8'
    invalid_res = client.post(f"/api/v1/sessions/{sid}/language", json={"language": "8"})
    assert invalid_res.status_code == 200
    data = invalid_res.json()
    assert data["state"] == "LANGUAGE_SELECT"
    assert "Please press 1 for English" in data["spoken_text"]


def test_get_session_status(client):
    res = client.post("/api/v1/sessions", json={})
    sid = res.json()["session_id"]

    status_res = client.get(f"/api/v1/sessions/{sid}")
    assert status_res.status_code == 200
    assert status_res.json()["session_id"] == sid
