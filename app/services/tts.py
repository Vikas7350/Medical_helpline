import io
import math
import struct
import wave
from app.core.config import settings
from app.core.logging import logger
from app.services.base import BaseTTSService


def create_silent_wav(duration_ms: int = 500, sample_rate: int = 8000) -> bytes:
    """Generate a minimal valid 8kHz mono WAV buffer (telephony standard)."""
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        silent_data = struct.pack(f"<{num_samples}h", *([0] * num_samples))
        wav_file.writeframes(silent_data)

    return buffer.getvalue()


def create_chime_wav(duration_ms: int = 2000, sample_rate: int = 8000) -> bytes:
    """Generate an audible, pleasant 8kHz mono WAV acoustic chime for telephony.

    Plays an ascending 3-note greeting chord (C5: 523Hz, E5: 659Hz, G5: 784Hz) with smooth
    envelope, followed by comfort tone, ensuring phone callers clearly hear audio on connection.
    """
    total_samples = int(sample_rate * (duration_ms / 1000.0))
    samples = []

    notes = [
        (0.0, 0.35, 523.25),
        (0.35, 0.70, 659.25),
        (0.70, 1.30, 783.99),
    ]

    for i in range(total_samples):
        t = i / float(sample_rate)
        sample_val = 0.0
        for start_t, end_t, freq in notes:
            if start_t <= t < end_t:
                note_pos = (t - start_t) / (end_t - start_t)
                attack = min(1.0, (t - start_t) / 0.01)
                decay = math.exp(-2.8 * note_pos)
                env = attack * decay
                sample_val += math.sin(2.0 * math.pi * freq * t) * env * 5500.0

        if 1.30 <= t < 2.0:
            env = 0.5 * (1.0 + math.cos(math.pi * (t - 1.30) / 0.70))
            sample_val += math.sin(2.0 * math.pi * 440.0 * t) * env * 700.0

        int_val = max(-32767, min(32767, int(sample_val)))
        samples.append(int_val)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    return buffer.getvalue()


class MockTTSService(BaseTTSService):
    """Mock Text-to-Speech service returning audible telephony-compliant WAV audio."""

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        duration_ms = min(max(len(text) * 40, 1000), 3000)
        logger.info(
            f"[MOCK_TTS] Generating simulated acoustic chime frame "
            f"({len(text)} chars, lang='{language}', {duration_ms}ms). Note: Real TTS provider is disabled."
        )
        return create_chime_wav(duration_ms=duration_ms)


class OpenAITTSService(BaseTTSService):
    """OpenAI TTS service providing natural voice synthesis in Hindi, Marathi, and English."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.api_key)
            response = await client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=text,
                response_format="wav",
            )
            raw_audio = await response.aread()

            # Resample 24kHz WAV from OpenAI down to 8kHz telephony standard if needed
            return self._resample_wav_to_8k(raw_audio)
        except Exception as e:
            safe_err = f"{type(e).__name__}: {e}"
            if self.api_key and self.api_key in safe_err:
                safe_err = safe_err.replace(self.api_key, "[REDACTED]")
            logger.error(f"OpenAI TTS synthesis error: {safe_err}")
            raise RuntimeError(f"Speech generation failed: OpenAI TTS error ({safe_err})")

    @staticmethod
    def _resample_wav_to_8k(wav_bytes: bytes) -> bytes:
        try:
            import numpy as np
            from scipy import signal

            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                sample_rate = wf.getframerate()
                n_channels = wf.getnchannels()
                frames = wf.readframes(wf.getnframes())

            audio_data = np.frombuffer(frames, dtype=np.int16)
            if n_channels > 1:
                audio_data = audio_data.reshape(-1, n_channels).mean(axis=1).astype(np.int16)

            if sample_rate != 8000:
                num_output_samples = int(len(audio_data) * 8000 / sample_rate)
                resampled = signal.resample(audio_data, num_output_samples).astype(np.int16)
            else:
                resampled = audio_data

            out_buf = io.BytesIO()
            with wave.open(out_buf, "wb") as out_wf:
                out_wf.setnchannels(1)
                out_wf.setsampwidth(2)
                out_wf.setframerate(8000)
                out_wf.writeframes(resampled.tobytes())

            return out_buf.getvalue()
        except Exception:
            return wav_bytes


class EdgeTTSService(BaseTTSService):
    """Microsoft Edge Neural TTS service supporting native Hindi, Marathi, and English."""

    VOICE_MAP = {
        "hi": "hi-IN-SwaraNeural",    # Native Hindi (Devanagari)
        "mr": "mr-IN-AarohiNeural",   # Native Marathi (Devanagari)
        "en": "en-IN-NeerjaNeural",   # Indian English
    }

    def __init__(self, voice_map: dict = None):
        self.voice_map = voice_map or self.VOICE_MAP

    def get_voice(self, language: str) -> str:
        lang = (language or "en").lower().strip()
        return self.voice_map.get(lang, self.voice_map.get("en", "en-IN-NeerjaNeural"))

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        voice = self.get_voice(language)
        try:
            import edge_tts

            comm = edge_tts.Communicate(text, voice)
            mp3_buf = bytearray()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    mp3_buf.extend(chunk["data"])

            if not mp3_buf:
                raise RuntimeError(f"Edge TTS returned empty audio stream for voice '{voice}'")

            return self._convert_mp3_to_8k_wav(bytes(mp3_buf))
        except Exception as e:
            if isinstance(e, RuntimeError) and "Speech generation failed" in str(e):
                raise
            logger.error(f"Edge TTS synthesis error for lang='{language}', voice='{voice}': {e}")
            raise RuntimeError(f"Speech generation failed: Edge TTS error ({e})")

    @staticmethod
    def _convert_mp3_to_8k_wav(mp3_bytes: bytes) -> bytes:
        import miniaudio
        import numpy as np
        from scipy import signal

        decoded = miniaudio.mp3_read_s16(mp3_bytes)
        samples = np.frombuffer(decoded.samples, dtype=np.int16)
        if decoded.nchannels > 1:
            samples = samples.reshape(-1, decoded.nchannels).mean(axis=1).astype(np.int16)
        if decoded.sample_rate != 8000:
            target_len = int(len(samples) * 8000 / decoded.sample_rate)
            samples = signal.resample(samples, target_len).astype(np.int16)

        out = io.BytesIO()
        with wave.open(out, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(samples.tobytes())
        return out.getvalue()


class DeepgramTTSService(BaseTTSService):
    """Deepgram Aura TTS service producing telephony-compliant speech."""

    def __init__(self, api_key: str, model: str = "aura-asteria-en"):
        self.api_key = api_key
        self.model = model

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        lang = (language or "en").lower().strip()
        # Deepgram Aura voices (aura-*-en) only support English.
        # Guard: Never send Hindi or Marathi to an English-only acoustic model.
        if lang in ("hi", "mr"):
            logger.warning(
                f"Deepgram Aura model '{self.model}' is English-only and does not support '{lang}'. "
                f"Automatically routing to EdgeTTSService for natural {lang} speech synthesis."
            )
            return await EdgeTTSService().synthesize(text, language=lang)

        try:
            import httpx

            url = f"https://api.deepgram.com/v1/speak?model={self.model}&encoding=linear16&sample_rate=8000&container=wav"
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {"text": text}

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    raw_audio = response.content
                    return OpenAITTSService._resample_wav_to_8k(raw_audio)
                else:
                    err_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(f"Deepgram TTS API error: {err_msg}")
                    raise RuntimeError(f"Speech generation failed: Deepgram API error ({err_msg})")
        except RuntimeError:
            raise
        except Exception as e:
            safe_err = f"{type(e).__name__}: {e}"
            if self.api_key and self.api_key in safe_err:
                safe_err = safe_err.replace(self.api_key, "[REDACTED]")
            logger.error(f"Deepgram TTS synthesis error: {safe_err}")
            raise RuntimeError(f"Speech generation failed: Deepgram TTS error ({safe_err})")


def get_tts_service() -> BaseTTSService:
    """Factory returning configured TTS provider."""
    provider = settings.TTS_PROVIDER.lower()
    if provider in ("grok", "xai"):
        logger.error(
            "xAI Grok does not provide a supported standalone REST TTS endpoint for telephony audio generation. "
            "Please configure TTS_PROVIDER to 'edge_tts', 'openai', 'deepgram', or 'mock'."
        )
        raise ValueError(
            "xAI Grok does not support speech synthesis (TTS). Grok is an LLM provider (LLM_PROVIDER=grok). "
            "Use TTS_PROVIDER='edge_tts', 'openai', 'deepgram', or 'mock'."
        )
    if provider in ("edge_tts", "edgetts", "edge"):
        return EdgeTTSService()
    if provider == "openai" and getattr(settings, "OPENAI_API_KEY", None):
        return OpenAITTSService(api_key=settings.OPENAI_API_KEY)
    if provider == "deepgram" and getattr(settings, "DEEPGRAM_API_KEY", None):
        return DeepgramTTSService(api_key=settings.DEEPGRAM_API_KEY)
    return MockTTSService()


