"""Unit tests for AI and Speech providers: xAI Grok LLM, OpenAI LLM, and TTS services."""

import asyncio
import io
import wave
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.config import settings
from app.services.llm import GrokLLMService, MockLLMService, OpenAILLMService, get_llm_service
from app.services.tts import DeepgramTTSService, EdgeTTSService, MockTTSService, OpenAITTSService, get_tts_service



# ---------------------------------------------------------------------------
# LLM Provider Selection Tests
# ---------------------------------------------------------------------------

def test_llm_provider_selection_grok(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "grok")
    monkeypatch.setattr(settings, "XAI_API_KEY", "xai-test-key-123")
    service = get_llm_service()
    assert isinstance(service, GrokLLMService)
    assert service.api_key == "xai-test-key-123"


def test_llm_provider_selection_xai_alias(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "xai")
    monkeypatch.setattr(settings, "XAI_API_KEY", "xai-test-key-456")
    service = get_llm_service()
    assert isinstance(service, GrokLLMService)
    assert service.api_key == "xai-test-key-456"


def test_llm_provider_selection_openai(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test-key-789")
    service = get_llm_service()
    assert isinstance(service, OpenAILLMService)


def test_llm_provider_selection_fallback_when_key_missing(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "grok")
    monkeypatch.setattr(settings, "XAI_API_KEY", "")
    service = get_llm_service()
    assert isinstance(service, MockLLMService)


def test_llm_provider_selection_mock_default(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mock")
    service = get_llm_service()
    assert isinstance(service, MockLLMService)


# ---------------------------------------------------------------------------
# Grok LLM Service Tests (Responses, Safety Guardrails, Error Handling)
# ---------------------------------------------------------------------------

def test_grok_llm_successful_response():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Please rest and drink plenty of fluids. Visit your nearest Primary Health Centre if symptoms persist."
                }
            }
        ]
    }

    service = GrokLLMService(api_key="xai-dummy-secret-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        result = asyncio.run(service.generate_guidance(
            symptom_text="I have mild body ache",
            language="en",
            triage_guidance="Rest and visit PHC if severe.",
        ))

        assert mock_post.called
        call_kwargs = mock_post.call_args.kwargs
        assert mock_post.call_args.args[0] == "https://api.x.ai/v1/chat/completions"
        assert "Bearer xai-dummy-secret-key" in call_kwargs["headers"]["Authorization"]
        assert call_kwargs["json"]["model"] == "grok-2-latest"
        assert "Primary Health Centre" in result


def test_grok_llm_guardrails_prevent_medication_prescription():
    """Verify safety guardrails catch any illicit drug prescription in LLM output."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    # LLM hallucinating a dosage / prescription:
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "You should take 500mg paracetamol tablets twice daily."
                }
            }
        ]
    }

    service = GrokLLMService(api_key="xai-dummy-secret-key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        result = asyncio.run(service.generate_guidance(
            symptom_text="I have a headache",
            language="en",
        ))

        # Guardrails must sanitize and replace with clinical safety disclaimer
        assert "500mg" not in result
        assert "paracetamol" not in result.lower()
        assert "qualified medical professional" in result or "Primary Health Centre" in result


def test_grok_llm_api_error_fallback(caplog):
    """Verify that a 401 or 500 API error falls back safely to deterministic mock triage."""
    fake_response = MagicMock()
    fake_response.status_code = 401
    fake_response.text = '{"error": {"message": "Incorrect API key provided"}}'

    secret_key = "xai-sensitive-api-token-should-never-leak"
    service = GrokLLMService(api_key=secret_key)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        result = asyncio.run(service.generate_guidance(
            symptom_text="तेज बुखार है",
            language="hi",
        ))

        # Fallback to offline clinical rule engine succeeds
        assert result is not None
        assert len(result) > 0
        # Critical security check: API key must NEVER be printed or exposed
        assert secret_key not in caplog.text


def test_grok_llm_network_exception_fallback(caplog):
    """Verify connection timeout/failure gracefully falls back without crashing."""
    secret_key = "xai-secret-connection-test"
    service = GrokLLMService(api_key=secret_key)

    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        result = asyncio.run(service.generate_guidance(
            symptom_text="I have severe chest pain",
            language="en",
        ))

        # Should fall back to mock service emergency guidance
        assert result is not None
        assert "108" in result or "emergency" in result.lower() or "Primary Health Centre" in result
        assert secret_key not in caplog.text


# ---------------------------------------------------------------------------
# TTS Provider Selection Tests
# ---------------------------------------------------------------------------

def test_tts_provider_selection_openai(monkeypatch):
    monkeypatch.setattr(settings, "TTS_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-valid-key")
    service = get_tts_service()
    assert isinstance(service, OpenAITTSService)


def test_tts_provider_selection_deepgram(monkeypatch):
    monkeypatch.setattr(settings, "TTS_PROVIDER", "deepgram")
    monkeypatch.setattr(settings, "DEEPGRAM_API_KEY", "dg-valid-key")
    service = get_tts_service()
    assert isinstance(service, DeepgramTTSService)


def test_tts_provider_selection_edge_tts(monkeypatch):
    monkeypatch.setattr(settings, "TTS_PROVIDER", "edge_tts")
    service = get_tts_service()
    assert isinstance(service, EdgeTTSService)

    monkeypatch.setattr(settings, "TTS_PROVIDER", "edgetts")
    service = get_tts_service()
    assert isinstance(service, EdgeTTSService)


def test_tts_provider_selection_mock_default(monkeypatch):
    monkeypatch.setattr(settings, "TTS_PROVIDER", "mock")
    service = get_tts_service()
    assert isinstance(service, MockTTSService)


def test_tts_provider_selection_rejects_grok(monkeypatch):
    """Verify that routing TTS through Grok is rejected with a clear ValueError."""
    monkeypatch.setattr(settings, "TTS_PROVIDER", "grok")
    with pytest.raises(ValueError, match="xAI Grok does not support speech synthesis"):
        get_tts_service()

    monkeypatch.setattr(settings, "TTS_PROVIDER", "xai")
    with pytest.raises(ValueError, match="xAI Grok does not support speech synthesis"):
        get_tts_service()


def test_openai_tts_error_does_not_beep(caplog):
    """When OpenAI TTS fails (e.g. 401 invalid key), it must report failure and NOT return a beep."""
    secret_key = "sk-proj-invalid-test-key"
    service = OpenAITTSService(api_key=secret_key)

    with patch("openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.audio.speech.create = AsyncMock(side_effect=Exception("401 invalid_api_key"))
        mock_openai_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="Speech generation failed"):
            asyncio.run(service.synthesize("Hello caller", language="en"))

        # Secret key must not leak into log
        assert secret_key not in caplog.text


def test_deepgram_tts_error_does_not_beep(caplog):
    """When Deepgram TTS fails on English, it must report failure and NOT return a beep."""
    secret_key = "dg-invalid-token"
    service = DeepgramTTSService(api_key=secret_key)

    fake_response = MagicMock()
    fake_response.status_code = 401
    fake_response.text = '{"err_code": "INVALID_AUTH"}'

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response

        with pytest.raises(RuntimeError, match="Speech generation failed"):
            asyncio.run(service.synthesize("Hello caller", language="en"))

        assert secret_key not in caplog.text


def test_mock_tts_returns_8k_wav():
    """Mock TTS generates telephony-compliant 8 kHz mono WAV audio."""
    service = MockTTSService()
    wav_bytes = asyncio.run(service.synthesize("Welcome to the helpline", language="en"))

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getframerate() == 8000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getnframes() > 0



def test_edge_tts_voice_selection_per_language():
    service = EdgeTTSService()
    # Explicit language-to-voice mapping validation:
    assert service.get_voice("hi") == "hi-IN-SwaraNeural"
    assert service.get_voice("mr") == "mr-IN-AarohiNeural"
    assert service.get_voice("en") == "en-IN-NeerjaNeural"
    # Fallback to Indian English for unrecognized language
    assert service.get_voice("other") == "en-IN-NeerjaNeural"


def test_edge_tts_audio_conversion_to_8k_wav():
    """Verify that EdgeTTSService outputs telephony-compliant 8 kHz mono 16-bit WAV."""
    service = EdgeTTSService()

    # Create dummy 16-bit PCM bytes and simulate conversion
    dummy_wav = asyncio.run(service.synthesize("नमस्ते", language="hi"))
    with wave.open(io.BytesIO(dummy_wav), "rb") as wf:
        assert wf.getframerate() == 8000
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getnframes() > 0


def test_edge_tts_error_does_not_beep():
    """When Edge TTS synthesis fails or stream is empty, raise RuntimeError (no silent beep)."""
    service = EdgeTTSService()
    with patch("edge_tts.Communicate") as mock_comm_cls:
        mock_instance = MagicMock()
        # Simulate empty stream
        async def empty_stream():
            if False:
                yield {}
        mock_instance.stream = empty_stream
        mock_comm_cls.return_value = mock_instance

        with pytest.raises(RuntimeError, match="Speech generation failed"):
            asyncio.run(service.synthesize("Hello", language="en"))


def test_deepgram_tts_routes_hindi_marathi_to_multilingual():
    """Deepgram Aura is English-only. Verify 'hi' and 'mr' are NOT sent to Deepgram aura-*-en."""
    service = DeepgramTTSService(api_key="dg-dummy-key", model="aura-asteria-en")

    with patch.object(EdgeTTSService, "synthesize", new_callable=AsyncMock) as mock_edge_synth, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:

        mock_edge_synth.return_value = b"RIFF_FAKE_WAV"

        # 1. Hindi input
        result_hi = asyncio.run(service.synthesize("नमस्ते", language="hi"))
        assert mock_edge_synth.called
        assert mock_edge_synth.call_args.kwargs["language"] == "hi"
        assert not mock_post.called

        # 2. Marathi input
        mock_edge_synth.reset_mock()
        result_mr = asyncio.run(service.synthesize("नमस्कार", language="mr"))
        assert mock_edge_synth.called
        assert mock_edge_synth.call_args.kwargs["language"] == "mr"
        assert not mock_post.called


def test_grok_llm_enforces_devanagari_for_hindi():
    """Verify Grok prompt enforces Devanagari script and accepts valid Hindi response."""
    service = GrokLLMService(api_key="xai-test-key")
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "कृपया आराम करें और नजदीकी प्राथमिक स्वास्थ्य केंद्र में डॉक्टर से मिलें।"
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        result = asyncio.run(service.generate_guidance(
            symptom_text="मुझे सिरदर्द है",
            language="hi",
            triage_guidance="प्राथमिक स्वास्थ्य केंद्र जाएं।",
        ))

        call_kwargs = mock_post.call_args.kwargs
        messages = call_kwargs["json"]["messages"]
        system_content = messages[0]["content"]
        assert "Devanagari" in system_content or "देवनागरी" in system_content
        assert "प्राथमिक स्वास्थ्य केंद्र" in result


def test_grok_llm_enforces_devanagari_for_marathi():
    """Verify Grok prompt enforces Devanagari script and accepts valid Marathi response."""
    service = GrokLLMService(api_key="xai-test-key")
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "कृपया विश्रांती घ्या आणि जवळच्या प्राथमिक आरोग्य केंद्रात डॉक्टरांचा सल्ला घ्या."
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        result = asyncio.run(service.generate_guidance(
            symptom_text="माझे डोके दुखत आहे",
            language="mr",
            triage_guidance="प्राथमिक आरोग्य केंद्राला भेट द्या.",
        ))

        call_kwargs = mock_post.call_args.kwargs
        messages = call_kwargs["json"]["messages"]
        system_content = messages[0]["content"]
        assert "Devanagari" in system_content or "देवनागरी" in system_content
        assert "प्राथमिक आरोग्य केंद्र" in result


def test_grok_llm_falls_back_if_non_devanagari_for_hindi():
    """If Grok returns Romanized Hindi (Hinglish) without Devanagari, fall back to offline clinical guidance."""
    service = GrokLLMService(api_key="xai-test-key")
    fake_response = MagicMock()
    fake_response.status_code = 200
    # Grok hallucinating Roman script:
    fake_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Aapko aaram karna chahiye aur doctor ke paas jana chahiye."
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = fake_response
        result = asyncio.run(service.generate_guidance(
            symptom_text="मुझे सिरदर्द है",
            language="hi",
        ))

        # Must fall back to verified Devanagari clinical guidance
        assert any("\u0900" <= ch <= "\u097f" for ch in result)
        assert "Aapko aaram" not in result


# ---------------------------------------------------------------------------
# STT Provider & Utterance Detector Tests
# ---------------------------------------------------------------------------

from app.services.stt import SpeechRecognitionSTTService, MockSTTService, get_stt_service
from app.telephony.audio import UtteranceDetector, pcm_to_wav


def test_stt_provider_selection(monkeypatch):
    monkeypatch.setattr(settings, "STT_PROVIDER", "speech_recognition")
    service = get_stt_service()
    assert isinstance(service, SpeechRecognitionSTTService)

    monkeypatch.setattr(settings, "STT_PROVIDER", "mock")
    mock_service = get_stt_service()
    assert isinstance(mock_service, MockSTTService)


def test_utterance_detector_buffers_chunks_until_trailing_silence():
    """Verify UtteranceDetector accumulates chunks and triggers on trailing silence."""
    detector = UtteranceDetector(
        sample_rate=8000,
        energy_threshold=300.0,
        trailing_silence_seconds=0.9,
        min_utterance_seconds=0.5,
        max_utterance_seconds=7.0,
        preroll_seconds=0.3,
    )

    silence_chunk = b"\x00" * 3200  # 0.2s of silence (RMS=0)
    speech_chunk = b"\x20\x10" * 1600  # 0.2s of speech (RMS > 300)

    # 1. Background silence should return None
    t0 = 1000.0
    res = detector.process_chunk(silence_chunk, now=t0)
    assert res is None
    assert detector.is_speaking is False

    # 2. Speech starts: 3 chunks (0.6s total speech > 0.5s min)
    res1 = detector.process_chunk(speech_chunk, now=t0 + 0.2)
    assert res1 is None
    assert detector.is_speaking is True

    res2 = detector.process_chunk(speech_chunk, now=t0 + 0.4)
    assert res2 is None

    res3 = detector.process_chunk(speech_chunk, now=t0 + 0.6)
    assert res3 is None

    # 3. Trailing silence begins: 4 chunks (0.8s < 0.9s)
    for i in range(4):
        res = detector.process_chunk(silence_chunk, now=t0 + 0.8 + (i * 0.2))
        assert res is None, f"Premature trigger at silence chunk {i + 1}"
        assert detector.is_speaking is True

    # 4. 5th silence chunk reaches 1.0s trailing silence >= 0.9s threshold
    utterance = detector.process_chunk(silence_chunk, now=t0 + 1.6)
    assert utterance is not None
    assert len(utterance) > 0
    # Utterance should contain speech chunks + pre-roll
    assert len(utterance) >= len(speech_chunk) * 3
    # Detector state must be reset for next utterance
    assert detector.is_speaking is False


def test_utterance_detector_max_duration_cutoff():
    """Verify detector cuts off continuous speech at max_utterance_seconds."""
    detector = UtteranceDetector(
        sample_rate=8000,
        energy_threshold=300.0,
        trailing_silence_seconds=0.9,
        min_utterance_seconds=0.5,
        max_utterance_seconds=3.0,  # 3.0s max for test speed
        preroll_seconds=0.2,
    )

    speech_chunk = b"\x20\x10" * 1600  # 0.2s of speech
    t0 = 1000.0

    # Feed 15 chunks (3.0s total)
    utterance = None
    for i in range(16):
        res = detector.process_chunk(speech_chunk, now=t0 + (i * 0.2))
        if res is not None:
            utterance = res
            break

    assert utterance is not None, "Detector should have triggered at max duration"
    assert detector.is_speaking is False


def test_utterance_detector_discards_sub_minimum_burst():
    """Short noise spike (< 0.5s) followed by silence must be discarded, not emitted as utterance."""
    detector = UtteranceDetector(
        sample_rate=8000,
        energy_threshold=300.0,
        trailing_silence_seconds=0.9,
        min_utterance_seconds=0.5,
    )

    speech_chunk = b"\x20\x10" * 1600  # 0.2s of noise spike
    silence_chunk = b"\x00" * 3200
    t0 = 1000.0

    # 1 short chunk of 0.2s
    detector.process_chunk(speech_chunk, now=t0)

    # Followed by 5 chunks of silence (1.0s >= 0.9s)
    final_res = None
    for i in range(5):
        res = detector.process_chunk(silence_chunk, now=t0 + 0.2 + (i * 0.2))
        if res is not None:
            final_res = res

    # Must be None because 0.2s < 0.5s min_utterance_seconds
    assert final_res is None
    assert detector.is_speaking is False


def test_utterance_detector_reset():
    """Detector reset clears state and buffered audio completely."""
    detector = UtteranceDetector(sample_rate=8000)
    speech_chunk = b"\x20\x10" * 1600
    detector.process_chunk(speech_chunk, now=100.0)
    assert detector.is_speaking is True

    detector.reset()
    assert detector.is_speaking is False
    assert len(detector.buffered_pcm) == 0


def test_speech_recognition_locales_mapping():
    """Verify explicit locale configuration for Hindi, Marathi, and English."""
    service = SpeechRecognitionSTTService()
    assert service.SUPPORTED_LOCALES["hi"] == "hi-IN"
    assert service.SUPPORTED_LOCALES["mr"] == "mr-IN"
    assert service.SUPPORTED_LOCALES["en"] == "en-IN"


def test_speech_recognition_empty_audio():
    """Empty or headerless bytes return empty string without errors."""
    service = SpeechRecognitionSTTService()
    res1 = asyncio.run(service.transcribe(b"", language="hi"))
    assert res1 == ""

    res2 = asyncio.run(service.transcribe(b"too_short_riff", language="mr"))
    assert res2 == ""


def test_speech_recognition_successful_transcription():
    """Verify SpeechRecognitionSTTService passes correct locale to Google recognizer."""
    service = SpeechRecognitionSTTService()
    dummy_wav = pcm_to_wav(b"\x20\x10" * 1600, sample_rate=8000)

    with patch("speech_recognition.Recognizer") as mock_rec_cls, \
         patch("speech_recognition.AudioFile") as mock_af:

        mock_recognizer = MagicMock()
        mock_rec_cls.return_value = mock_recognizer
        mock_recognizer.record.return_value = MagicMock()
        mock_recognizer.recognize_google.return_value = "मुझे तेज बुखार है"

        result = asyncio.run(service.transcribe(dummy_wav, language="hi"))
        assert result == "मुझे तेज बुखार है"
        mock_recognizer.recognize_google.assert_called_once()
        assert mock_recognizer.recognize_google.call_args.kwargs["language"] == "hi-IN"


def test_speech_recognition_unknown_value_error_returns_empty():
    """UnknownValueError (silence/unintelligible) returns empty string without crashing."""
    import speech_recognition as sr
    service = SpeechRecognitionSTTService()
    dummy_wav = pcm_to_wav(b"\x00" * 3200, sample_rate=8000)

    with patch("speech_recognition.Recognizer") as mock_rec_cls, \
         patch("speech_recognition.AudioFile"):

        mock_recognizer = MagicMock()
        mock_rec_cls.return_value = mock_recognizer
        mock_recognizer.record.return_value = MagicMock()
        mock_recognizer.recognize_google.side_effect = sr.UnknownValueError()

        result = asyncio.run(service.transcribe(dummy_wav, language="hi"))
        assert result == ""


def test_speech_recognition_request_error_returns_empty():
    """RequestError (network failure) logs cleanly and returns empty string."""
    import speech_recognition as sr
    service = SpeechRecognitionSTTService()
    dummy_wav = pcm_to_wav(b"\x20\x10" * 1600, sample_rate=8000)

    with patch("speech_recognition.Recognizer") as mock_rec_cls, \
         patch("speech_recognition.AudioFile"):

        mock_recognizer = MagicMock()
        mock_rec_cls.return_value = mock_recognizer
        mock_recognizer.record.return_value = MagicMock()
        mock_recognizer.recognize_google.side_effect = sr.RequestError("Recognition server unavailable")

        result = asyncio.run(service.transcribe(dummy_wav, language="mr"))
        assert result == ""


def test_speech_recognition_timeout_handling():
    """Recognition timeout triggers gracefully without hanging the event loop."""
    import time
    service = SpeechRecognitionSTTService(timeout=0.05)
    dummy_wav = pcm_to_wav(b"\x20\x10" * 1600, sample_rate=8000)

    with patch("speech_recognition.Recognizer") as mock_rec_cls, \
         patch("speech_recognition.AudioFile"):

        mock_recognizer = MagicMock()
        mock_rec_cls.return_value = mock_recognizer
        mock_recognizer.record.return_value = MagicMock()

        def slow_recognize(*args, **kwargs):
            time.sleep(0.2)
            return "too slow"

        mock_recognizer.recognize_google.side_effect = slow_recognize

        result = asyncio.run(service.transcribe(dummy_wav, language="en"))
        assert result == ""


