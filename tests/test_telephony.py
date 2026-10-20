import base64
import hashlib
import hmac
import json
import pytest
from app.core.config import settings
from app.telephony.audio import chunk_pcm_audio, pcm_to_wav, wav_to_pcm, calculate_pcm_energy


def test_telephony_webhook_new_call(client):
    payload = {
        "CallSid": "EXOTEL_CALL_12345",
        "From": "+919876543210",
        "CallStatus": "ringing",
    }
    response = client.post("/api/v1/telephony/webhook", data=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["session_id"] == "EXOTEL_CALL_12345"
    assert "English" in data["spoken_text"]
    assert data["action"] == "gather"


def test_telephony_webhook_dtmf_digit(client):
    # Call connected, caller presses '2' for Hindi
    payload = {
        "CallSid": "EXOTEL_CALL_DTMF_TEST",
        "From": "+919876543210",
        "CallStatus": "in-progress",
        "Digits": "2",
    }
    response = client.post("/api/v1/telephony/webhook", data=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "hi"
    assert data["state"] == "SYMPTOM_INPUT"


def test_telephony_webhook_disconnect(client):
    payload = {
        "CallSid": "EXOTEL_CALL_DISCONNECT_TEST",
        "From": "+919876543210",
        "CallStatus": "completed",
    }
    response = client.post("/api/v1/telephony/webhook", data=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "hangup"


def test_telephony_signature_validation(client, monkeypatch):
    monkeypatch.setattr(settings, "TELEPHONY_PROVIDER", "exotel")
    monkeypatch.setattr(settings, "TELEPHONY_WEBHOOK_SECRET", "super_secret_key_123")

    body_bytes = b'{"CallSid": "TEST_SIG_CALL", "Digits": "1"}'
    valid_sig = hmac.new(b"super_secret_key_123", body_bytes, hashlib.sha256).hexdigest()

    # 1. Valid signature
    res_valid = client.post(
        "/api/v1/telephony/webhook",
        content=body_bytes,
        headers={"Content-Type": "application/json", "x-exotel-signature": valid_sig},
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "success"

    # 2. Invalid signature
    res_invalid = client.post(
        "/api/v1/telephony/webhook",
        content=body_bytes,
        headers={"Content-Type": "application/json", "x-exotel-signature": "bogus_signature"},
    )
    assert res_invalid.status_code == 200
    assert res_invalid.json()["status"] == "error"
    assert "Invalid webhook signature" in res_invalid.json()["message"]


# ============================================================================
# Exotel Voicebot Applet Tests: Dynamic URL, WebSocket Protocol, Audio & DTMF
# ============================================================================

def test_exotel_voicebot_dynamic_endpoint_get(client):
    """Verify Exotel Voicebot Applet dynamic URL endpoint returns target WSS URL on GET."""
    response = client.get("/api/v1/telephony/voicebot?sample-rate=8000&CallSid=EX_CALL_DYNAMIC_1")
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert data["url"].startswith("ws://") or data["url"].startswith("wss://")
    assert "sample-rate=8000" in data["url"]
    assert "session_id=EX_CALL_DYNAMIC_1" in data["url"]
    assert "/api/v1/telephony/stream" in data["url"]


def test_exotel_voicebot_dynamic_endpoint_post(client):
    """Verify Exotel Voicebot Applet dynamic URL endpoint parses form-data on POST."""
    form_data = {
        "CallSid": "EX_CALL_POST_888",
        "From": "+919876543210",
        "To": "+918000000000",
    }
    response = client.post("/api/v1/telephony/voicebot", data=form_data)
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "session_id=EX_CALL_POST_888" in data["url"]


def test_exotel_voicebot_dynamic_endpoint_custom_base_url(client, monkeypatch):
    """Verify dynamic endpoint honors EXOTEL_STREAM_BASE_URL when deployed behind reverse proxy/ngrok."""
    custom_wss = "wss://helpline.ruralhealth.gov.in/api/v1/telephony/stream"
    monkeypatch.setattr(settings, "EXOTEL_STREAM_BASE_URL", custom_wss)

    response = client.get("/api/v1/telephony/voicebot?sample-rate=16000&CallSid=PROD_CALL_1")
    assert response.status_code == 200
    data = response.json()
    assert data["url"].startswith(custom_wss)
    assert "sample-rate=16000" in data["url"]
    assert "session_id=PROD_CALL_1" in data["url"]


def test_audio_pcm_chunking_and_alignment():
    """Verify raw PCM audio chunking strictly conforms to Exotel's Voicebot specification."""
    # 1. 5000 bytes of dummy 16-bit PCM
    dummy_pcm = b"\x01\x00" * 2500  # 5000 bytes
    chunks = chunk_pcm_audio(dummy_pcm, chunk_size=3200)

    assert len(chunks) == 2
    for chunk in chunks:
        # Every chunk must be a multiple of 320 bytes
        assert len(chunk) % 320 == 0
        # Every chunk must meet minimum chunk size (3200 bytes)
        assert len(chunk) >= 3200

    # 2. WAV to PCM and PCM to WAV conversion
    wav_bytes = pcm_to_wav(dummy_pcm, sample_rate=8000)
    assert wav_bytes.startswith(b"RIFF")
    extracted_pcm = wav_to_pcm(wav_bytes)
    assert extracted_pcm == dummy_pcm

    # 3. Energy calculation
    silent_pcm = b"\x00" * 3200
    assert calculate_pcm_energy(silent_pcm) == 0.0


def test_websocket_stream_basic_auth_validation(client, monkeypatch):
    """Verify Exotel WebSocket Basic Authentication validation."""
    monkeypatch.setattr(settings, "TELEPHONY_PROVIDER", "exotel")
    monkeypatch.setattr(settings, "EXOTEL_API_KEY", "test_key_abc")
    monkeypatch.setattr(settings, "EXOTEL_API_TOKEN", "test_token_xyz")
    monkeypatch.setattr(settings, "EXOTEL_STREAM_REQUIRE_AUTH", True)

    # 1. Reject missing credentials when auth is required
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/telephony/stream"):
            pass

    # 2. Reject incorrect credentials
    bad_b64 = base64.b64encode(b"wrong_key:wrong_token").decode("ascii")
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/telephony/stream", headers={"Authorization": f"Basic {bad_b64}"}):
            pass

    # 3. Accept valid base64 credentials: 'test_key_abc:test_token_xyz'
    valid_b64 = base64.b64encode(b"test_key_abc:test_token_xyz").decode("ascii")
    headers = {"Authorization": f"Basic {valid_b64}"}

    with client.websocket_connect("/api/v1/telephony/stream", headers=headers) as ws:
        # Should connect successfully and send connected/start
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "stream-auth-test",
            "start": {
                "call_sid": "CALL_AUTH_TEST",
                "stream_sid": "stream-auth-test",
                "media_format": {"sample_rate": "8000"},
            },
        }))
        # Verify initial greeting audio sent by server
        data = json.loads(ws.receive_text())
        assert data["event"] == "media"
        assert data["stream_sid"] == "stream-auth-test"


def test_websocket_stream_exotel_full_bidirectional_protocol(client):
    """Verify end-to-end Exotel Voicebot bidirectional WebSocket protocol.

    Tests:
    - Initial connection & Exotel 'connected' event
    - Exotel 'start' event with metadata (stream_sid, call_sid, media_format)
    - Outgoing greeting in compliant 16-bit PCM chunks (multiples of 320 bytes, >= 3200 bytes)
    - Exotel 'mark' event for playback confirmation
    - Exotel 'dtmf' event (keypad selection)
    - Exotel 'media' audio stream event (spoken symptom)
    - Exotel 'stop' event for graceful disconnection
    """
    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        # 1. Exotel sends 'connected'
        ws.send_text(json.dumps({"event": "connected"}))

        # 2. Exotel sends 'start'
        ws.send_text(json.dumps({
            "event": "start",
            "sequence_number": 1,
            "stream_sid": "stream-sid-live-001",
            "start": {
                "call_sid": "EXOTEL_CALL_LIVE_001",
                "stream_sid": "stream-sid-live-001",
                "from": "+919876543210",
                "to": "+918000000000",
                "media_format": {
                    "encoding": "audio/x-raw",
                    "sample_rate": "8000",
                    "bit_rate": "16",
                },
            },
        }))

        # 3. Server should stream greeting audio media chunk(s) and mark
        first_msg = json.loads(ws.receive_text())
        assert first_msg["event"] == "media"
        assert first_msg["stream_sid"] == "stream-sid-live-001"
        assert set(first_msg.keys()) == {"event", "stream_sid", "media"}
        assert set(first_msg["media"].keys()) == {"payload"}
        assert "sequence_number" not in first_msg
        assert "chunk" not in first_msg["media"]
        assert "timestamp" not in first_msg["media"]

        # Validate audio payload format
        audio_chunk = base64.b64decode(first_msg["media"]["payload"])
        assert len(audio_chunk) % 320 == 0
        assert len(audio_chunk) >= 3200

        # Drain any remaining greeting chunks until greeting mark is reached
        received_mark = False
        greeting_mark_msg = None
        while not received_mark:
            next_msg = json.loads(ws.receive_text())
            if next_msg["event"] == "media":
                assert set(next_msg.keys()) == {"event", "stream_sid", "media"}
                assert set(next_msg["media"].keys()) == {"payload"}
                assert "sequence_number" not in next_msg
            elif next_msg["event"] == "mark" and next_msg.get("mark", {}).get("name") == "greeting":
                greeting_mark_msg = next_msg
                received_mark = True

        assert received_mark is True
        assert greeting_mark_msg is not None
        assert greeting_mark_msg["stream_sid"] == "stream-sid-live-001"
        assert set(greeting_mark_msg.keys()) == {"event", "stream_sid", "mark"}
        assert greeting_mark_msg["mark"] == {"name": "greeting"}
        assert "sequence_number" not in greeting_mark_msg

        # 4. Caller presses '2' on keypad for Hindi (Exotel DTMF event)
        ws.send_text(json.dumps({
            "event": "dtmf",
            "sequence_number": 2,
            "stream_sid": "stream-sid-live-001",
            "dtmf": {
                "digit": "2",
                "duration": "100",
            },
        }))

        # 5. Server responds with clear event (to stop any playing audio) followed by response audio
        clear_msg = json.loads(ws.receive_text())
        assert clear_msg["event"] == "clear"
        assert clear_msg["stream_sid"] == "stream-sid-live-001"

        # Drain turn 1 response audio chunks
        dtmf_turn_mark = False
        while not dtmf_turn_mark:
            dtmf_resp = json.loads(ws.receive_text())
            if dtmf_resp["event"] == "mark":
                dtmf_turn_mark = True

        assert dtmf_turn_mark is True

        # 6. Caller speaks symptom (Exotel sends media audio chunks followed by trailing silence)
        sample_audio = b"\x10\x20" * 1600  # Non-zero 16-bit PCM samples (energy > 300)
        speech_b64 = base64.b64encode(sample_audio).decode("ascii")
        for i in range(3):
            ws.send_text(json.dumps({
                "event": "media",
                "sequence_number": 3 + i,
                "stream_sid": "stream-sid-live-001",
                "media": {
                    "chunk": i + 1,
                    "timestamp": str(100 + i * 200),
                    "payload": speech_b64,
                },
            }))

        # Send trailing silence chunks to complete utterance
        silence_audio = b"\x00" * 3200
        silence_b64 = base64.b64encode(silence_audio).decode("ascii")
        for i in range(5):
            ws.send_text(json.dumps({
                "event": "media",
                "sequence_number": 6 + i,
                "stream_sid": "stream-sid-live-001",
                "media": {
                    "chunk": 4 + i,
                    "timestamp": str(700 + i * 200),
                    "payload": silence_b64,
                },
            }))

        # Drain turn 2 response audio
        symptom_turn_mark = False
        while not symptom_turn_mark:
            symptom_resp = json.loads(ws.receive_text())
            if symptom_resp["event"] == "mark":
                symptom_turn_mark = True

        assert symptom_turn_mark is True

        # 7. Exotel sends 'stop' event (call ended)
        ws.send_text(json.dumps({
            "event": "stop",
            "sequence_number": 10,
            "stream_sid": "stream-sid-live-001",
            "stop": {
                "call_sid": "EXOTEL_CALL_LIVE_001",
                "account_sid": "exotel_acc",
                "reason": "callended",
            },
        }))


def test_websocket_stream_mock_compatibility(client):
    """Verify backward compatibility with mock simulator and legacy text events."""
    with client.websocket_connect("/api/v1/telephony/stream/mock_compat_session") as ws:
        # In mock mode, server sends media audio and also greeting text
        received_greeting_text = False
        for _ in range(5):
            msg = json.loads(ws.receive_text())
            if msg.get("event") == "greeting" and "Welcome" in msg.get("text", ""):
                received_greeting_text = True
                break

        assert received_greeting_text is True

        # Send mock DTMF format (top-level digit)
        ws.send_text(json.dumps({"event": "dtmf", "digit": "1"}))

        received_response_text = False
        for _ in range(5):
            msg = json.loads(ws.receive_text())
            if msg.get("event") == "response":
                received_response_text = True
                assert "symptoms" in msg.get("text", "").lower()
                break

        assert received_response_text is True


def test_websocket_stream_ip_whitelisting(client, monkeypatch):
    """Verify Exotel IP Whitelisting mode (connecting without Authorization header when auth not required)."""
    monkeypatch.setattr(settings, "TELEPHONY_PROVIDER", "exotel")
    monkeypatch.setattr(settings, "EXOTEL_STREAM_REQUIRE_AUTH", False)

    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "ip-white-stream",
            "start": {
                "call_sid": "IP_WHITE_CALL",
                "stream_sid": "ip-white-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "media"
        assert msg["stream_sid"] == "ip-white-stream"


def test_exotel_voicebot_dynamic_endpoint_no_credential_leak(client, monkeypatch):
    """Verify dynamic voicebot endpoint never exposes API keys or tokens in returned URL."""
    monkeypatch.setattr(settings, "TELEPHONY_PROVIDER", "exotel")
    monkeypatch.setattr(settings, "EXOTEL_API_KEY", "super_secret_exotel_key")
    monkeypatch.setattr(settings, "EXOTEL_API_TOKEN", "super_secret_exotel_token")

    res = client.get("/api/v1/telephony/voicebot")
    assert res.status_code == 200
    data = res.json()
    url = data["url"]

    assert "super_secret_exotel_key" not in url
    assert "super_secret_exotel_token" not in url
    assert "@" not in url
    assert "sample-rate=8000" in url


def test_dtmf_language_selection_multilingual(client):
    """Verify DTMF language selection for 1 (English), 2 (Hindi), and 3 (Marathi)."""
    # 1. English (Digit 1)
    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "lang-test-en",
            "start": {"call_sid": "CALL_LANG_EN", "stream_sid": "lang-test-en"},
        }))
        # Drain greeting media & mark
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        # Send DTMF 1
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "lang-test-en",
            "dtmf": {"digit": "1"},
        }))
        clear_m = json.loads(ws.receive_text())
        assert clear_m["event"] == "clear"

        # Drain media until turn mark
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

    # 2. Hindi (Digit 2)
    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "lang-test-hi",
            "start": {"call_sid": "CALL_LANG_HI", "stream_sid": "lang-test-hi"},
        }))
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        # Send DTMF 2
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "lang-test-hi",
            "dtmf": {"digit": "2"},
        }))
        clear_m = json.loads(ws.receive_text())
        assert clear_m["event"] == "clear"

        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

    # 3. Marathi (Digit 3)
    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "lang-test-mr",
            "start": {"call_sid": "CALL_LANG_MR", "stream_sid": "lang-test-mr"},
        }))
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        # Send DTMF 3
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "lang-test-mr",
            "dtmf": {"digit": "3"},
        }))
        clear_m = json.loads(ws.receive_text())
        assert clear_m["event"] == "clear"

        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break


def test_sanitizing_formatter_redacts_credentials_and_phi():
    """Verify SanitizingFormatter redacts API keys, Bearer tokens, passwords, phones, and emails."""
    import logging
    from app.core.logging import SanitizingFormatter

    formatter = SanitizingFormatter("%(message)s")

    def sanitize(msg: str) -> str:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=(),
            exc_info=None,
        )
        return formatter.format(record)

    # 1. Phone number redaction
    assert "[REDACTED_PHONE]" in sanitize("Caller dialed from +919876543210 with fever")
    assert "[REDACTED_PHONE]" in sanitize("Number is 9876543210")

    # 2. Email redaction
    assert "[REDACTED_EMAIL]" in sanitize("Contact patient at patient.rural@example.com")

    # 3. Basic auth redaction
    assert "Basic [REDACTED_CREDENTIAL]" in sanitize("Handshake header: Basic dXNlcjpwYXNz")

    # 4. Bearer token redaction
    assert "Bearer [REDACTED_CREDENTIAL]" in sanitize("Header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz")

    # 5. API keys / secrets
    assert "api_key=[REDACTED]" in sanitize("Failed call with api_key=sk-abc123456789")
    assert "password=[REDACTED]" in sanitize("db config password='super_secret_db_pass'")

    # 6. Embedded URL credentials
    assert "wss://[REDACTED_USER]:[REDACTED_PASS]@telephony.exotel.com" in sanitize(
        "Connecting to wss://my_key:my_token@telephony.exotel.com/stream"
    )


def test_exotel_incoming_silence_during_greeting_does_not_abort_call(client):
    """Regression test: Exotel incoming silence chunks during greeting must NOT cause false STT triggers or call disconnect."""
    from app.engine.conversation import conversation_manager
    from app.engine.state_machine import ConversationState

    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        # 1. Connected & Start
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "silence-test-stream",
            "start": {
                "call_sid": "CALL_SILENCE_REGRESSION",
                "stream_sid": "silence-test-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))

        # Drain greeting media & mark
        greeting_received = False
        while not greeting_received:
            msg = json.loads(ws.receive_text())
            if msg.get("event") == "mark" and msg.get("mark", {}).get("name") == "greeting":
                greeting_received = True

        assert greeting_received is True

        # 2. Exotel streams 5 consecutive silence chunks (ambient microphone sound)
        silence_pcm = b"\x00" * 3200
        silence_b64 = base64.b64encode(silence_pcm).decode("ascii")

        for i in range(5):
            ws.send_text(json.dumps({
                "event": "media",
                "sequence_number": i + 2,
                "stream_sid": "silence-test-stream",
                "media": {
                    "chunk": i + 1,
                    "timestamp": str(i * 200),
                    "payload": silence_b64,
                },
            }))

        # 3. Verify session state is still LANGUAGE_SELECT and unrecognized_count is 0
        ctx = conversation_manager.get_context("CALL_SILENCE_REGRESSION")
        assert ctx is not None
        assert ctx.state == ConversationState.LANGUAGE_SELECT
        assert ctx.unrecognized_count == 0
        assert ctx.is_completed is False

        # 4. Caller now presses DTMF '2' for Hindi -> smoothly transitions to SYMPTOM_INPUT
        ws.send_text(json.dumps({
            "event": "dtmf",
            "sequence_number": 8,
            "stream_sid": "silence-test-stream",
            "dtmf": {"digit": "2"},
        }))

        clear_msg = json.loads(ws.receive_text())
        assert clear_msg["event"] == "clear"

        # Drain Hindi response audio & mark
        turn_mark_received = False
        while not turn_mark_received:
            msg = json.loads(ws.receive_text())
            if msg.get("event") == "mark":
                turn_mark_received = True

        assert turn_mark_received is True
        assert ctx.state == ConversationState.SYMPTOM_INPUT
        assert ctx.language == "hi"


def test_mock_stt_does_not_claim_silent_audio_is_speech():
    """Verify MockSTTService returns empty string on silent audio and does not claim it is speech."""
    import asyncio
    from app.services.stt import MockSTTService
    from app.telephony.audio import pcm_to_wav

    stt = MockSTTService()

    # 1. Digital silence (all zeros)
    silent_pcm = b"\x00" * 3200
    silent_wav = pcm_to_wav(silent_pcm, sample_rate=8000)
    transcript = asyncio.run(stt.transcribe(silent_wav, language="en"))
    assert transcript == ""

    # 2. Simulated voice samples (non-zero energy)
    speech_pcm = b"\x10\x20" * 1600
    speech_wav = pcm_to_wav(speech_pcm, sample_rate=8000)
    transcript_en = asyncio.run(stt.transcribe(speech_wav, language="en"))
    assert transcript_en == "I have a fever for three days"

    transcript_hi = asyncio.run(stt.transcribe(speech_wav, language="hi"))
    assert transcript_hi == "मुझे तीन दिन से तेज बुखार है"


def test_websocket_send_audio_stops_immediately_on_disconnect():
    """Verify send_audio_to_exotel stops immediately when socket is disconnected without looping or crashing."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from starlette.websockets import WebSocketState
    from app.telephony.websocket_stream import TelephonyStreamHandler

    mock_ws = MagicMock()
    mock_ws.client_state = WebSocketState.DISCONNECTED
    mock_ws.application_state = WebSocketState.DISCONNECTED
    mock_ws.send_text = AsyncMock()

    # Attempt to send 10 chunks of audio
    dummy_audio = b"\x00" * 32000  # 10 chunks
    sent_count, next_seq, is_completed = asyncio.run(
        TelephonyStreamHandler.send_audio_to_exotel(
            websocket=mock_ws,
            audio_bytes=dummy_audio,
            stream_sid="test-stream",
            seq_start=1,
        )
    )

    # Must immediately abort: 0 chunks sent, send_text never called
    assert sent_count == 0
    assert next_seq == 1
    assert is_completed is False
    assert mock_ws.send_text.call_count == 0


def test_mock_stt_discards_acoustic_chime_echo():
    """Regression test: MockSTTService must detect acoustic chime audio and return empty string, not canned speech."""
    import asyncio
    from app.services.stt import MockSTTService
    from app.services.tts import create_chime_wav

    stt = MockSTTService()
    chime_wav = create_chime_wav(duration_ms=2000, sample_rate=8000)
    transcript = asyncio.run(stt.transcribe(chime_wav, language="en"))
    assert transcript == "", f"Expected empty transcript for acoustic chime, got '{transcript}'"


def test_send_audio_and_mark_exact_outbound_exotel_format():
    """Verify outbound media and mark messages strictly adhere to the official Exotel AgentStream protocol."""
    import asyncio
    import json
    from unittest.mock import AsyncMock, MagicMock
    from starlette.websockets import WebSocketState
    from app.telephony.websocket_stream import TelephonyStreamHandler
    from app.telephony.audio import pcm_to_wav

    mock_ws = MagicMock()
    mock_ws.client_state = WebSocketState.CONNECTED
    mock_ws.application_state = WebSocketState.CONNECTED
    mock_ws.send_text = AsyncMock()

    dummy_pcm = b"\x10\x20" * 1600  # 3200 bytes (1 chunk)
    dummy_wav = pcm_to_wav(dummy_pcm, sample_rate=8000)

    # 1. Test send_audio_to_exotel outbound structure
    sent_count, next_seq, is_completed = asyncio.run(
        TelephonyStreamHandler.send_audio_to_exotel(
            websocket=mock_ws,
            audio_bytes=dummy_wav,
            stream_sid="stream-exotel-123",
            pace_stream=False,
        )
    )
    assert sent_count == 1
    assert is_completed is True
    assert mock_ws.send_text.call_count == 1

    call_arg = mock_ws.send_text.call_args[0][0]
    media_msg = json.loads(call_arg)

    # Official Exotel AgentStream media structure:
    # { "event": "media", "stream_sid": state.stream_sid, "media": { "payload": base64.b64encode(chunk).decode("ascii") } }
    assert set(media_msg.keys()) == {"event", "stream_sid", "media"}
    assert media_msg["event"] == "media"
    assert media_msg["stream_sid"] == "stream-exotel-123"
    assert set(media_msg["media"].keys()) == {"payload"}
    assert "sequence_number" not in media_msg
    assert "chunk" not in media_msg["media"]
    assert "timestamp" not in media_msg["media"]

    # 2. Test send_mark outbound structure:
    # {"event": "mark", "stream_sid": state.stream_sid, "mark": {"name": "greeting"}}
    mock_ws.send_text.reset_mock()
    success = asyncio.run(
        TelephonyStreamHandler.send_mark(
            websocket=mock_ws,
            stream_sid="stream-exotel-123",
            name="greeting",
        )
    )
    assert success is True
    assert mock_ws.send_text.call_count == 1

    mark_call_arg = mock_ws.send_text.call_args[0][0]
    mark_msg = json.loads(mark_call_arg)

    assert set(mark_msg.keys()) == {"event", "stream_sid", "mark"}
    assert mark_msg["event"] == "mark"
    assert mark_msg["stream_sid"] == "stream-exotel-123"
    assert mark_msg["mark"] == {"name": "greeting"}
    assert "sequence_number" not in mark_msg


def test_exotel_outbound_format_and_clear_event_on_barge_in(client):
    """Verify outbound audio adheres to documented schema (no sequence_number/chunk/timestamp) and clear event flushes buffer on barge-in."""
    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "seq-monotonic-stream",
            "start": {
                "call_sid": "CALL_SEQ_MONOTONIC",
                "stream_sid": "seq-monotonic-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))

        # Read only the first 2 chunks of greeting audio
        msg1 = json.loads(ws.receive_text())
        assert msg1["event"] == "media"
        assert set(msg1.keys()) == {"event", "stream_sid", "media"}
        assert set(msg1["media"].keys()) == {"payload"}
        assert "sequence_number" not in msg1
        assert "chunk" not in msg1["media"]
        assert "timestamp" not in msg1["media"]

        msg2 = json.loads(ws.receive_text())
        assert msg2["event"] == "media"
        assert set(msg2.keys()) == {"event", "stream_sid", "media"}
        assert set(msg2["media"].keys()) == {"payload"}
        assert "sequence_number" not in msg2

        # Mid-stream barge-in: caller presses DTMF '1' while greeting is actively streaming
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "seq-monotonic-stream",
            "dtmf": {"digit": "1"},
        }))

        # Read messages until the 'clear' event is received (draining any pre-queued greeting chunks)
        clear_msg = None
        while True:
            msg = json.loads(ws.receive_text())
            if msg.get("event") == "media":
                assert set(msg.keys()) == {"event", "stream_sid", "media"}
                assert set(msg["media"].keys()) == {"payload"}
                assert "sequence_number" not in msg
            elif msg.get("event") == "clear":
                clear_msg = msg
                break

        assert clear_msg is not None
        assert set(clear_msg.keys()) == {"event", "stream_sid"}
        assert clear_msg["event"] == "clear"
        assert clear_msg["stream_sid"] == "seq-monotonic-stream"

        # Next response chunks MUST strictly adhere to the outbound schema
        resp_chunk1 = json.loads(ws.receive_text())
        assert resp_chunk1["event"] == "media"
        assert set(resp_chunk1.keys()) == {"event", "stream_sid", "media"}
        assert set(resp_chunk1["media"].keys()) == {"payload"}
        assert "sequence_number" not in resp_chunk1



def test_echo_suppressed_during_active_greeting_playback(client):
    """Regression test: Inbound audio arriving while server is streaming greeting must be suppressed and not trigger STT."""
    from app.engine.conversation import conversation_manager
    from app.engine.state_machine import ConversationState

    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "echo-suppression-stream",
            "start": {
                "call_sid": "CALL_ECHO_SUPPRESSION",
                "stream_sid": "echo-suppression-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))

        # Read chunk 1
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "media"

        # Inject simulated chime echo (RMS > 500) while greeting playback is still active
        echo_pcm = b"\x20\x10" * 1600
        echo_b64 = base64.b64encode(echo_pcm).decode("ascii")
        ws.send_text(json.dumps({
            "event": "media",
            "stream_sid": "echo-suppression-stream",
            "media": {"chunk": 1, "payload": echo_b64},
        }))

        # Greeting should NOT be interrupted; drain greeting until mark
        greeting_mark_seen = False
        while not greeting_mark_seen:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark" and m.get("mark", {}).get("name") == "greeting":
                greeting_mark_seen = True

        assert greeting_mark_seen is True

        # Verify state is still LANGUAGE_SELECT and unrecognized_count did not increment
        ctx = conversation_manager.get_context("CALL_ECHO_SUPPRESSION")
        assert ctx is not None
        assert ctx.state == ConversationState.LANGUAGE_SELECT
        assert ctx.unrecognized_count == 0


def test_non_language_speech_in_language_select_ignored_without_retry_penalty(client):
    """Regression test: Spoken non-language noise in LANGUAGE_SELECT must not increment unrecognized_count or terminate call."""
    from app.engine.conversation import conversation_manager
    from app.engine.state_machine import ConversationState

    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "lang-select-noise-stream",
            "start": {
                "call_sid": "CALL_LANG_NOISE",
                "stream_sid": "lang-select-noise-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))

        # Drain greeting
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        # Send text simulating spoken words like "I have a cough" (non-language keyword)
        non_lang_speech = base64.b64encode(b"I have a fever for three days").decode("ascii")
        ws.send_text(json.dumps({
            "event": "media",
            "stream_sid": "lang-select-noise-stream",
            "media": {"chunk": 1, "payload": non_lang_speech},
        }))

        ctx = conversation_manager.get_context("CALL_LANG_NOISE")
        assert ctx.state == ConversationState.LANGUAGE_SELECT
        assert ctx.unrecognized_count == 0  # Not penalized!

        # Caller now presses '1' for English
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "lang-select-noise-stream",
            "dtmf": {"digit": "1"},
        }))

        clear_msg = json.loads(ws.receive_text())
        assert clear_msg["event"] == "clear"

        # Drain English prompt
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        assert ctx.state == ConversationState.SYMPTOM_INPUT
        assert ctx.language == "en"


def test_spoken_symptom_in_hindi_advances_to_duration_input(client):
    """Caller selects Hindi (DTMF 2), speaks symptoms in chunks, and state advances to DURATION_INPUT."""
    from app.engine.conversation import conversation_manager
    from app.engine.state_machine import ConversationState

    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "hi-speech-stream",
            "start": {
                "call_sid": "CALL_HI_SPEECH_ADVANCE",
                "stream_sid": "hi-speech-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))

        # Drain greeting
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        # Select Hindi with DTMF 2
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "hi-speech-stream",
            "dtmf": {"digit": "2"},
        }))

        clear_msg = json.loads(ws.receive_text())
        assert clear_msg["event"] == "clear"

        # Drain Hindi prompt
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        ctx = conversation_manager.get_context("CALL_HI_SPEECH_ADVANCE")
        assert ctx.state == ConversationState.SYMPTOM_INPUT
        assert ctx.language == "hi"

        # Caller speaks symptom: 3 speech chunks followed by 5 silence chunks
        speech_b64 = base64.b64encode(b"\x20\x10" * 1600).decode("ascii")
        silence_b64 = base64.b64encode(b"\x00" * 3200).decode("ascii")

        for i in range(3):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "hi-speech-stream",
                "media": {"chunk": i + 1, "payload": speech_b64},
            }))

        for i in range(5):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "hi-speech-stream",
                "media": {"chunk": 4 + i, "payload": silence_b64},
            }))

        # Drain response to symptom input
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        assert ctx.state == ConversationState.DURATION_INPUT
        assert len(ctx.symptoms_text) > 0


def test_spoken_symptom_in_marathi_advances_to_duration_input(client):
    """Caller selects Marathi (DTMF 3), speaks symptoms in chunks, and state advances to DURATION_INPUT."""
    from app.engine.conversation import conversation_manager
    from app.engine.state_machine import ConversationState

    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "mr-speech-stream",
            "start": {
                "call_sid": "CALL_MR_SPEECH_ADVANCE",
                "stream_sid": "mr-speech-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))

        # Drain greeting
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        # Select Marathi with DTMF 3
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "mr-speech-stream",
            "dtmf": {"digit": "3"},
        }))

        clear_msg = json.loads(ws.receive_text())
        assert clear_msg["event"] == "clear"

        # Drain Marathi prompt
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        ctx = conversation_manager.get_context("CALL_MR_SPEECH_ADVANCE")
        assert ctx.state == ConversationState.SYMPTOM_INPUT
        assert ctx.language == "mr"

        # Caller speaks symptom: 3 speech chunks followed by 5 silence chunks
        speech_b64 = base64.b64encode(b"\x20\x10" * 1600).decode("ascii")
        silence_b64 = base64.b64encode(b"\x00" * 3200).decode("ascii")

        for i in range(3):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "mr-speech-stream",
                "media": {"chunk": i + 1, "payload": speech_b64},
            }))

        for i in range(5):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "mr-speech-stream",
                "media": {"chunk": 4 + i, "payload": silence_b64},
            }))

        # Drain response to symptom input
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        assert ctx.state == ConversationState.DURATION_INPUT
        assert len(ctx.symptoms_text) > 0


def test_spoken_symptom_in_english_advances_to_duration_input(client):
    """Caller selects English (DTMF 1), speaks symptoms in chunks, and state advances to DURATION_INPUT."""
    from app.engine.conversation import conversation_manager
    from app.engine.state_machine import ConversationState

    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "en-speech-stream",
            "start": {
                "call_sid": "CALL_EN_SPEECH_ADVANCE",
                "stream_sid": "en-speech-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))

        # Drain greeting
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        # Select English with DTMF 1
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "en-speech-stream",
            "dtmf": {"digit": "1"},
        }))

        clear_msg = json.loads(ws.receive_text())
        assert clear_msg["event"] == "clear"

        # Drain English prompt
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        ctx = conversation_manager.get_context("CALL_EN_SPEECH_ADVANCE")
        assert ctx.state == ConversationState.SYMPTOM_INPUT
        assert ctx.language == "en"

        # Caller speaks symptom: 3 speech chunks followed by 5 silence chunks
        speech_b64 = base64.b64encode(b"\x20\x10" * 1600).decode("ascii")
        silence_b64 = base64.b64encode(b"\x00" * 3200).decode("ascii")

        for i in range(3):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "en-speech-stream",
                "media": {"chunk": i + 1, "payload": speech_b64},
            }))

        for i in range(5):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "en-speech-stream",
                "media": {"chunk": 4 + i, "payload": silence_b64},
            }))

        # Drain response to symptom input
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        assert ctx.state == ConversationState.DURATION_INPUT
        assert len(ctx.symptoms_text) > 0


def test_websocket_disconnect_during_utterance_handling(client):
    """Verify WebSocket disconnect during incoming audio streaming cleans up without crashing."""
    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "disconnect-mid-speech-stream",
            "start": {
                "call_sid": "CALL_DISCONNECT_MID_SPEECH",
                "stream_sid": "disconnect-mid-speech-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))

        # Read first greeting chunk and immediately close socket
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "media"
        ws.close()


def test_websocket_spoken_duration_advances_to_severity(client):
    """Verify incoming speech during DURATION_INPUT advances state machine over WebSocket stream."""
    from app.engine.conversation import conversation_manager
    from app.engine.state_machine import ConversationState

    with client.websocket_connect("/api/v1/telephony/stream") as ws:
        ws.send_text(json.dumps({"event": "connected"}))
        ws.send_text(json.dumps({
            "event": "start",
            "stream_sid": "duration-speech-stream",
            "start": {
                "call_sid": "CALL_DURATION_SPEECH_ADVANCE",
                "stream_sid": "duration-speech-stream",
                "media_format": {"sample_rate": "8000"},
            },
        }))

        # Drain greeting
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        # Select Hindi with DTMF 2
        ws.send_text(json.dumps({
            "event": "dtmf",
            "stream_sid": "duration-speech-stream",
            "dtmf": {"digit": "2"},
        }))

        clear_msg = json.loads(ws.receive_text())
        assert clear_msg["event"] == "clear"

        # Drain Hindi prompt
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        ctx = conversation_manager.get_context("CALL_DURATION_SPEECH_ADVANCE")
        assert ctx.state == ConversationState.SYMPTOM_INPUT
        assert ctx.language == "hi"

        # 1. Caller speaks symptom
        speech_b64 = base64.b64encode(b"\x20\x10" * 1600).decode("ascii")
        silence_b64 = base64.b64encode(b"\x00" * 3200).decode("ascii")

        for i in range(3):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "duration-speech-stream",
                "media": {"chunk": i + 1, "payload": speech_b64},
            }))
        for i in range(5):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "duration-speech-stream",
                "media": {"chunk": 4 + i, "payload": silence_b64},
            }))

        # Drain response to symptom input
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        assert ctx.state == ConversationState.DURATION_INPUT

        # 2. Caller speaks duration: MockSTT in Hindi returns "मुझे तीन दिन से तेज बुखार है" which has "तीन दिन" (3 days)
        for i in range(3):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "duration-speech-stream",
                "media": {"chunk": 10 + i, "payload": speech_b64},
            }))
        for i in range(5):
            ws.send_text(json.dumps({
                "event": "media",
                "stream_sid": "duration-speech-stream",
                "media": {"chunk": 13 + i, "payload": silence_b64},
            }))

        # Drain response to duration input
        while True:
            m = json.loads(ws.receive_text())
            if m.get("event") == "mark":
                break

        assert ctx.state == ConversationState.SEVERITY_INPUT
        assert ctx.duration_days == 3



