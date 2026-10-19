import io
from typing import Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.base import BaseSTTService
from app.telephony.audio import calculate_pcm_energy, is_acoustic_chime_tone, wav_to_pcm


class MockSTTService(BaseSTTService):
    """Mock Speech-to-Text service for zero-credential local runs and testing."""

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        if not audio_bytes or len(audio_bytes) == 0:
            return ""

        # If audio_bytes is utf-8 encoded text passed directly in simulation
        try:
            decoded = audio_bytes.decode("utf-8").strip()
            if decoded:
                logger.info(f"[MOCK_STT] Using direct text input simulation: '{decoded}'")
                return decoded
        except Exception:
            pass

        # Check audio energy: do not claim silent mock audio or ambient line noise is real speech
        pcm_data = wav_to_pcm(audio_bytes)
        energy = calculate_pcm_energy(pcm_data)
        if energy < 300.0:
            logger.debug(
                f"[MOCK_STT] Incoming audio is silence/background noise (RMS={energy:.1f} < 300.0). "
                "No speech detected. (Silent audio is not speech)."
            )
            return ""

        # Check if the incoming audio is the server's own synthesized chime or periodic prompt tone
        if is_acoustic_chime_tone(pcm_data):
            logger.info(
                f"[MOCK_STT] Inbound audio identified as acoustic chime tone/prompt feedback (RMS={energy:.1f}). "
                "Discarding prompt chime echo; no caller speech recognized."
            )
            return ""

        # Simulated default recognition based on language when non-silent simulated speech is supplied
        if language == "hi":
            transcript = "मुझे तीन दिन से तेज बुखार है"
        elif language == "mr":
            transcript = "मला तीन दिवसांपासून ताप आहे"
        else:
            transcript = "I have a fever for three days"

        logger.info(
            f"[MOCK_STT] Simulated speech output active for mock testing (language='{language}', RMS={energy:.1f}). "
            f"Returning simulated transcript: '{transcript}'. Note: Real STT provider is disabled; actual caller voice is not recognized."
        )
        return transcript


import asyncio


class SpeechRecognitionSTTService(BaseSTTService):
    """Local SpeechRecognition provider utilizing Google Speech API with per-language locales."""

    SUPPORTED_LOCALES = {
        "en": "en-IN",
        "hi": "hi-IN",
        "mr": "mr-IN",
    }

    def __init__(self, timeout: float = 7.0):
        self.timeout = timeout

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        if not audio_bytes or len(audio_bytes) < 44:
            return ""

        lang = (language or "en").lower().strip()
        lang_code = self.SUPPORTED_LOCALES.get(lang, "en-IN")

        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()

            def _sync_recognize() -> str:
                with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
                    audio_data = recognizer.record(source)
                return recognizer.recognize_google(audio_data, language=lang_code)

            try:
                text = await asyncio.wait_for(
                    asyncio.to_thread(_sync_recognize),
                    timeout=self.timeout,
                )
                clean_text = text.strip() if text else ""
                if clean_text:
                    logger.info(
                        f"[STT] Recognition successful: locale='{lang_code}', transcript='{clean_text}'"
                    )
                return clean_text
            except sr.UnknownValueError:
                logger.info(
                    f"[STT] No speech detected in audio for locale='{lang_code}' (silence or unintelligible noise)"
                )
                return ""
            except sr.RequestError as req_err:
                logger.error(
                    f"[STT] Google Speech Recognition network error for locale='{lang_code}': {req_err}"
                )
                return ""
            except asyncio.TimeoutError:
                logger.error(
                    f"[STT] Speech recognition timed out after {self.timeout}s for locale='{lang_code}'"
                )
                return ""

        except Exception as e:
            logger.error(f"[STT] SpeechRecognition audio processing error: {type(e).__name__}: {e}")
            return ""



def get_stt_service() -> BaseSTTService:
    """Factory returning configured STT provider."""
    provider = settings.STT_PROVIDER.lower()
    if provider == "speech_recognition":
        return SpeechRecognitionSTTService()
    return MockSTTService()
