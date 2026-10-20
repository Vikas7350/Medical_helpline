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


def test_spoken_symptom_descriptions_work(client):
    """Spoken symptom descriptions in English, Hindi, and Marathi advance correctly."""
    # English non-emergency
    res_en = client.post("/api/v1/sessions", json={})
    sid_en = res_en.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid_en}/language", json={"language": "1"})
    t_en = client.post(f"/api/v1/sessions/{sid_en}/turn", json={"user_input": "I have a mild runny nose and cough"})
    assert t_en.status_code == 200
    assert t_en.json()["state"] == "DURATION_INPUT"
    assert "How many days" in t_en.json()["spoken_text"]

    # Hindi non-emergency
    res_hi = client.post("/api/v1/sessions", json={})
    sid_hi = res_hi.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid_hi}/language", json={"language": "2"})
    t_hi = client.post(f"/api/v1/sessions/{sid_hi}/turn", json={"user_input": "मुझे हल्की सर्दी और जुकाम है"})
    assert t_hi.status_code == 200
    assert t_hi.json()["state"] == "DURATION_INPUT"
    assert "कितने दिनों से है" in t_hi.json()["spoken_text"]

    # Marathi non-emergency
    res_mr = client.post("/api/v1/sessions", json={})
    sid_mr = res_mr.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid_mr}/language", json={"language": "3"})
    t_mr = client.post(f"/api/v1/sessions/{sid_mr}/turn", json={"user_input": "मला थोडा ताप आणि सर्दी आहे"})
    assert t_mr.status_code == 200
    assert t_mr.json()["state"] == "DURATION_INPUT"
    assert "किती दिवसांपासून आहे" in t_mr.json()["spoken_text"]

    # Emergency speech bypasses follow-up questions immediately
    res_emg = client.post("/api/v1/sessions", json={})
    sid_emg = res_emg.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid_emg}/language", json={"language": "1"})
    t_emg = client.post(f"/api/v1/sessions/{sid_emg}/turn", json={"user_input": "severe chest pain and shortness of breath"})
    assert t_emg.status_code == 200
    assert t_emg.json()["state"] == "GUIDANCE_DELIVERED"
    assert t_emg.json()["is_completed"] is True
    assert t_emg.json()["triage"]["is_emergency"] is True


def test_spoken_duration_answers_in_all_three_languages(client):
    """Callers can answer duration questions by speaking naturally in EN, HI, and MR."""
    # 1. English: "three days"
    res1 = client.post("/api/v1/sessions", json={})
    sid1 = res1.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid1}/language", json={"language": "1"})
    client.post(f"/api/v1/sessions/{sid1}/turn", json={"user_input": "mild cough"})
    turn_dur_en = client.post(f"/api/v1/sessions/{sid1}/turn", json={"user_input": "three days"})
    assert turn_dur_en.status_code == 200
    assert turn_dur_en.json()["state"] == "SEVERITY_INPUT"
    assert "How severe" in turn_dur_en.json()["spoken_text"]

    # English: "yesterday"
    res1b = client.post("/api/v1/sessions", json={})
    sid1b = res1b.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid1b}/language", json={"language": "1"})
    client.post(f"/api/v1/sessions/{sid1b}/turn", json={"user_input": "mild cough"})
    turn_dur_en2 = client.post(f"/api/v1/sessions/{sid1b}/turn", json={"user_input": "since yesterday"})
    assert turn_dur_en2.status_code == 200
    assert turn_dur_en2.json()["state"] == "SEVERITY_INPUT"

    # 2. Hindi: "तीन दिन"
    res2 = client.post("/api/v1/sessions", json={})
    sid2 = res2.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid2}/language", json={"language": "2"})
    client.post(f"/api/v1/sessions/{sid2}/turn", json={"user_input": "हल्की सर्दी है"})
    turn_dur_hi = client.post(f"/api/v1/sessions/{sid2}/turn", json={"user_input": "तीन दिन से है"})
    assert turn_dur_hi.status_code == 200
    assert turn_dur_hi.json()["state"] == "SEVERITY_INPUT"
    assert "तकलीफ कितनी है" in turn_dur_hi.json()["spoken_text"]

    # Hindi: "दो दिन"
    res2b = client.post("/api/v1/sessions", json={})
    sid2b = res2b.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid2b}/language", json={"language": "2"})
    client.post(f"/api/v1/sessions/{sid2b}/turn", json={"user_input": "हल्की सर्दी है"})
    turn_dur_hi2 = client.post(f"/api/v1/sessions/{sid2b}/turn", json={"user_input": "दो दिन"})
    assert turn_dur_hi2.status_code == 200
    assert turn_dur_hi2.json()["state"] == "SEVERITY_INPUT"

    # 3. Marathi: "तीन दिवस"
    res3 = client.post("/api/v1/sessions", json={})
    sid3 = res3.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid3}/language", json={"language": "3"})
    client.post(f"/api/v1/sessions/{sid3}/turn", json={"user_input": "थोडं अंग दुखत आहे"})
    turn_dur_mr = client.post(f"/api/v1/sessions/{sid3}/turn", json={"user_input": "तीन दिवस झाले"})
    assert turn_dur_mr.status_code == 200
    assert turn_dur_mr.json()["state"] == "SEVERITY_INPUT"
    assert "त्रास किती तीव्र आहे" in turn_dur_mr.json()["spoken_text"]

    # Marathi: "दोन दिवस"
    res3b = client.post("/api/v1/sessions", json={})
    sid3b = res3b.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid3b}/language", json={"language": "3"})
    client.post(f"/api/v1/sessions/{sid3b}/turn", json={"user_input": "थोडं अंग दुखत आहे"})
    turn_dur_mr2 = client.post(f"/api/v1/sessions/{sid3b}/turn", json={"user_input": "दोन दिवस"})
    assert turn_dur_mr2.status_code == 200
    assert turn_dur_mr2.json()["state"] == "SEVERITY_INPUT"


def test_spoken_severity_answers_in_all_three_languages(client):
    """Callers can answer severity questions by speaking naturally in EN, HI, and MR."""
    # 1. English: "mild"
    res1 = client.post("/api/v1/sessions", json={})
    sid1 = res1.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid1}/language", json={"language": "1"})
    client.post(f"/api/v1/sessions/{sid1}/turn", json={"user_input": "mild cold"})
    client.post(f"/api/v1/sessions/{sid1}/turn", json={"user_input": "one day"})
    turn_sev_en = client.post(f"/api/v1/sessions/{sid1}/turn", json={"user_input": "it is mild"})
    assert turn_sev_en.status_code == 200
    assert turn_sev_en.json()["state"] == "GUIDANCE_DELIVERED"
    assert turn_sev_en.json()["is_completed"] is True
    assert turn_sev_en.json()["triage"]["urgency_category"] == "general_guidance"

    # English: "severe" -> triggers prompt assessment escalation
    res1b = client.post("/api/v1/sessions", json={})
    sid1b = res1b.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid1b}/language", json={"language": "1"})
    client.post(f"/api/v1/sessions/{sid1b}/turn", json={"user_input": "headache"})
    client.post(f"/api/v1/sessions/{sid1b}/turn", json={"user_input": "one day"})
    turn_sev_en2 = client.post(f"/api/v1/sessions/{sid1b}/turn", json={"user_input": "very severe"})
    assert turn_sev_en2.status_code == 200
    assert turn_sev_en2.json()["state"] == "GUIDANCE_DELIVERED"
    assert turn_sev_en2.json()["triage"]["urgency_category"] == "prompt_assessment"

    # 2. Hindi: "हल्का"
    res2 = client.post("/api/v1/sessions", json={})
    sid2 = res2.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid2}/language", json={"language": "2"})
    client.post(f"/api/v1/sessions/{sid2}/turn", json={"user_input": "सर्दी जुकाम"})
    client.post(f"/api/v1/sessions/{sid2}/turn", json={"user_input": "दो दिन"})
    turn_sev_hi = client.post(f"/api/v1/sessions/{sid2}/turn", json={"user_input": "हल्का दर्द है"})
    assert turn_sev_hi.status_code == 200
    assert turn_sev_hi.json()["state"] == "GUIDANCE_DELIVERED"
    assert turn_sev_hi.json()["is_completed"] is True

    # Hindi: "बहुत तेज" -> triggers escalation
    res2b = client.post("/api/v1/sessions", json={})
    sid2b = res2b.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid2b}/language", json={"language": "2"})
    client.post(f"/api/v1/sessions/{sid2b}/turn", json={"user_input": "सिरदर्द"})
    client.post(f"/api/v1/sessions/{sid2b}/turn", json={"user_input": "एक दिन"})
    turn_sev_hi2 = client.post(f"/api/v1/sessions/{sid2b}/turn", json={"user_input": "बहुत तेज दर्द है"})
    assert turn_sev_hi2.status_code == 200
    assert turn_sev_hi2.json()["state"] == "GUIDANCE_DELIVERED"
    assert turn_sev_hi2.json()["triage"]["urgency_category"] == "prompt_assessment"

    # 3. Marathi: "हलका"
    res3 = client.post("/api/v1/sessions", json={})
    sid3 = res3.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid3}/language", json={"language": "3"})
    client.post(f"/api/v1/sessions/{sid3}/turn", json={"user_input": "सर्दी खोकला"})
    client.post(f"/api/v1/sessions/{sid3}/turn", json={"user_input": "दोन दिवस"})
    turn_sev_mr = client.post(f"/api/v1/sessions/{sid3}/turn", json={"user_input": "हलका त्रास आहे"})
    assert turn_sev_mr.status_code == 200
    assert turn_sev_mr.json()["state"] == "GUIDANCE_DELIVERED"
    assert turn_sev_mr.json()["is_completed"] is True

    # Marathi: "तीव्र" -> triggers escalation
    res3b = client.post("/api/v1/sessions", json={})
    sid3b = res3b.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid3b}/language", json={"language": "3"})
    client.post(f"/api/v1/sessions/{sid3b}/turn", json={"user_input": "डोकेदुखी"})
    client.post(f"/api/v1/sessions/{sid3b}/turn", json={"user_input": "एक दिवस"})
    turn_sev_mr2 = client.post(f"/api/v1/sessions/{sid3b}/turn", json={"user_input": "तीव्र वेदना आहेत"})
    assert turn_sev_mr2.status_code == 200
    assert turn_sev_mr2.json()["state"] == "GUIDANCE_DELIVERED"
    assert turn_sev_mr2.json()["triage"]["urgency_category"] == "prompt_assessment"


def test_spoken_yes_no_answers_normalized():
    """Verify parse_yes_no normalizes supported spoken equivalents across EN, HI, MR and DTMF."""
    from app.engine.parsers import parse_yes_no
    from app.engine.state_machine import ConversationContext, ConversationState, HelplineStateMachine

    # Direct parser checks
    assert parse_yes_no("yes") is True
    assert parse_yes_no("yeah") is True
    assert parse_yes_no("sure") is True
    assert parse_yes_no("1") is True
    assert parse_yes_no("हाँ") is True
    assert parse_yes_no("जी हाँ") is True
    assert parse_yes_no("होय") is True
    assert parse_yes_no("हो") is True

    assert parse_yes_no("no") is False
    assert parse_yes_no("nope") is False
    assert parse_yes_no("2") is False
    assert parse_yes_no("नहीं") is False
    assert parse_yes_no("जी नहीं") is False
    assert parse_yes_no("नहीं है") is False
    assert parse_yes_no("नाही") is False
    assert parse_yes_no("काही नाही") is False

    # Ambiguous / unclear returns None
    assert parse_yes_no("maybe") is None
    assert parse_yes_no("cough") is None
    assert parse_yes_no("three days") is None

    # State machine EMERGENCY_CONFIRMATION handler
    ctx_yes = ConversationContext(session_id="test_emg_yes", state=ConversationState.EMERGENCY_CONFIRMATION, language="hi")
    res_yes = HelplineStateMachine.process_turn(ctx_yes, "हाँ मुझे सीने में दर्द है")
    assert res_yes.next_state == ConversationState.GUIDANCE_DELIVERED
    assert ctx_yes.emergency_confirmed is True
    assert res_yes.triage_assessment.is_emergency is True

    ctx_no = ConversationContext(session_id="test_emg_no", state=ConversationState.EMERGENCY_CONFIRMATION, language="hi", symptoms_text="सर्दी")
    res_no = HelplineStateMachine.process_turn(ctx_no, "नहीं ऐसा कुछ नहीं है")
    assert res_no.next_state == ConversationState.GUIDANCE_DELIVERED
    assert ctx_no.emergency_confirmed is False


def test_unclear_answers_trigger_clarification_without_advancing(client):
    """Unclear or invalid speech does not advance state; repeats/clarifies question."""
    res = client.post("/api/v1/sessions", json={})
    sid = res.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid}/language", json={"language": "2"})
    client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "हल्की सर्दी है"})

    # In DURATION_INPUT: Send random unclear text
    turn_unclear1 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "सेब और केला"})
    assert turn_unclear1.status_code == 200
    assert turn_unclear1.json()["state"] == "DURATION_INPUT"  # State NOT advanced!
    assert "हम आपकी बात ठीक से समझ नहीं पाए" in turn_unclear1.json()["spoken_text"]
    assert "कितने दिनों से है" in turn_unclear1.json()["spoken_text"]
    assert turn_unclear1.json()["should_hangup"] is False

    # Second unclear attempt
    turn_unclear2 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "कुछ भी नहीं समझ आया"})
    assert turn_unclear2.status_code == 200
    assert turn_unclear2.json()["state"] == "DURATION_INPUT"  # Still in DURATION_INPUT!
    assert turn_unclear2.json()["should_hangup"] is False

    # Now provide valid spoken duration: advances to SEVERITY_INPUT
    turn_valid = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "तीन दिन"})
    assert turn_valid.status_code == 200
    assert turn_valid.json()["state"] == "SEVERITY_INPUT"
    assert "तकलीफ कितनी है" in turn_valid.json()["spoken_text"]

    # In SEVERITY_INPUT: Send unclear text
    turn_unclear_sev = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "पता नहीं"})
    assert turn_unclear_sev.status_code == 200
    assert turn_unclear_sev.json()["state"] == "SEVERITY_INPUT"  # State NOT advanced!
    assert "हम आपकी बात ठीक से समझ नहीं पाए" in turn_unclear_sev.json()["spoken_text"]

    # Provide valid spoken severity: advances to GUIDANCE_DELIVERED
    turn_valid_sev = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "हल्की है"})
    assert turn_valid_sev.status_code == 200
    assert turn_valid_sev.json()["state"] == "GUIDANCE_DELIVERED"
    assert turn_valid_sev.json()["is_completed"] is True


def test_dtmf_inputs_remain_fully_functional(client):
    """Keypad inputs (1, 2, 3) remain fully functional as fallbacks in every state."""
    res = client.post("/api/v1/sessions", json={})
    sid = res.json()["session_id"]

    # DTMF 1 for English
    l_res = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "1", "is_dtmf": True})
    assert l_res.json()["state"] == "SYMPTOM_INPUT"

    # Caller speaks symptom
    s_res = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "headache and runny nose"})
    assert s_res.json()["state"] == "DURATION_INPUT"

    # DTMF 2 for >= 3 days
    d_res = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "2", "is_dtmf": True})
    assert d_res.json()["state"] == "SEVERITY_INPUT"

    # DTMF 3 for severe
    sev_res = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "3", "is_dtmf": True})
    assert sev_res.json()["state"] == "GUIDANCE_DELIVERED"
    assert sev_res.json()["is_completed"] is True


def test_spoken_repeat_and_dtmf_zero_in_all_states(client):
    """Spoken repeat and DTMF 0 work in DURATION_INPUT and SEVERITY_INPUT without disconnecting."""
    res = client.post("/api/v1/sessions", json={})
    sid = res.json()["session_id"]
    client.post(f"/api/v1/sessions/{sid}/language", json={"language": "2"})
    client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "हल्की खांसी"})

    # In DURATION_INPUT: Spoken repeat in Hindi
    rep1 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "दोहराएं"})
    assert rep1.status_code == 200
    assert rep1.json()["state"] == "DURATION_INPUT"
    assert "कितने दिनों से है" in rep1.json()["spoken_text"]
    assert rep1.json()["should_hangup"] is False

    # In DURATION_INPUT: DTMF 0
    rep2 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "0", "is_dtmf": True})
    assert rep2.status_code == 200
    assert rep2.json()["state"] == "DURATION_INPUT"
    assert rep2.json()["should_hangup"] is False

    # Advance to SEVERITY_INPUT
    client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "दो दिन"})

    # In SEVERITY_INPUT: Spoken repeat
    rep3 = client.post(f"/api/v1/sessions/{sid}/turn", json={"user_input": "फिर से बोलो"})
    assert rep3.status_code == 200
    assert rep3.json()["state"] == "SEVERITY_INPUT"
    assert "तकलीफ कितनी है" in rep3.json()["spoken_text"]
    assert rep3.json()["should_hangup"] is False


def test_complete_natural_spoken_conversation_all_languages(client):
    """Complete IVR conversation purely using natural spoken answers in English, Hindi, and Marathi."""
    # 1. English conversation purely by speaking
    res_en = client.post("/api/v1/sessions", json={})
    sid_en = res_en.json()["session_id"]
    # Spoken language select
    t0_en = client.post(f"/api/v1/sessions/{sid_en}/turn", json={"user_input": "English"})
    assert t0_en.json()["state"] == "SYMPTOM_INPUT"
    # Spoken symptoms
    t1_en = client.post(f"/api/v1/sessions/{sid_en}/turn", json={"user_input": "I have a mild sore throat"})
    assert t1_en.json()["state"] == "DURATION_INPUT"
    # Spoken duration
    t2_en = client.post(f"/api/v1/sessions/{sid_en}/turn", json={"user_input": "two days"})
    assert t2_en.json()["state"] == "SEVERITY_INPUT"
    # Spoken severity
    t3_en = client.post(f"/api/v1/sessions/{sid_en}/turn", json={"user_input": "it is mild"})
    assert t3_en.json()["state"] == "GUIDANCE_DELIVERED"
    assert t3_en.json()["is_completed"] is True

    # 2. Hindi conversation purely by speaking
    res_hi = client.post("/api/v1/sessions", json={})
    sid_hi = res_hi.json()["session_id"]
    # Spoken language select
    t0_hi = client.post(f"/api/v1/sessions/{sid_hi}/turn", json={"user_input": "हिंदी"})
    assert t0_hi.json()["state"] == "SYMPTOM_INPUT"
    # Spoken symptoms
    t1_hi = client.post(f"/api/v1/sessions/{sid_hi}/turn", json={"user_input": "हल्का सिरदर्द और जुकाम है"})
    assert t1_hi.json()["state"] == "DURATION_INPUT"
    # Spoken duration
    t2_hi = client.post(f"/api/v1/sessions/{sid_hi}/turn", json={"user_input": "तीन दिन"})
    assert t2_hi.json()["state"] == "SEVERITY_INPUT"
    # Spoken severity
    t3_hi = client.post(f"/api/v1/sessions/{sid_hi}/turn", json={"user_input": "मध्यम"})
    assert t3_hi.json()["state"] == "GUIDANCE_DELIVERED"
    assert t3_hi.json()["is_completed"] is True

    # 3. Marathi conversation purely by speaking
    res_mr = client.post("/api/v1/sessions", json={})
    sid_mr = res_mr.json()["session_id"]
    # Spoken language select
    t0_mr = client.post(f"/api/v1/sessions/{sid_mr}/turn", json={"user_input": "मराठी"})
    assert t0_mr.json()["state"] == "SYMPTOM_INPUT"
    # Spoken symptoms
    t1_mr = client.post(f"/api/v1/sessions/{sid_mr}/turn", json={"user_input": "मला घसा खवखवणे आणि थोडा खोकला आहे"})
    assert t1_mr.json()["state"] == "DURATION_INPUT"
    # Spoken duration
    t2_mr = client.post(f"/api/v1/sessions/{sid_mr}/turn", json={"user_input": "दोन दिवस"})
    assert t2_mr.json()["state"] == "SEVERITY_INPUT"
    # Spoken severity
    t3_mr = client.post(f"/api/v1/sessions/{sid_mr}/turn", json={"user_input": "हलका"})
    assert t3_mr.json()["state"] == "GUIDANCE_DELIVERED"
    assert t3_mr.json()["is_completed"] is True

