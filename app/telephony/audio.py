"""Audio processing utilities for Exotel Voicebot linear PCM streaming."""

import io
import math
import struct
import wave
from typing import List, Optional



def wav_to_pcm(audio_bytes: bytes) -> bytes:
    """Extract raw 16-bit linear PCM mono samples from a WAV container.

    If audio_bytes does not contain a RIFF header, returns the bytes as-is.
    """
    if not audio_bytes:
        return b""
    if audio_bytes.startswith(b"RIFF"):
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                return wf.readframes(wf.getnframes())
        except Exception:
            # Fallback: standard 44-byte WAV header strip
            return audio_bytes[44:] if len(audio_bytes) > 44 else audio_bytes
    return audio_bytes


def pcm_to_wav(
    pcm_bytes: bytes,
    sample_rate: int = 8000,
    channels: int = 1,
    sampwidth: int = 2,
) -> bytes:
    """Wrap raw 16-bit little-endian linear PCM audio samples into a standard WAV container.

    Used when passing raw Exotel stream audio to speech recognizers expecting WAV headers.
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def chunk_pcm_audio(
    pcm_bytes: bytes,
    chunk_size: int = 3200,
    min_chunk_size: int = 3200,
) -> List[bytes]:
    """Split linear PCM bytes into chunks strictly conforming to Exotel's Voicebot specification:

    1. Minimum chunk size: 3.2k (3200 bytes, ~100ms at 16kHz or ~200ms at 8kHz).
    2. Maximum chunk size: 100k.
    3. Every chunk MUST be a multiple of 320 bytes.
    Any trailing chunk is padded with 0x00 silence to preserve 320-byte alignment and minimum chunk size.
    """
    if not pcm_bytes:
        return []

    # Ensure chunk_size is a multiple of 320
    if chunk_size % 320 != 0:
        chunk_size = max((chunk_size // 320) * 320, 320)

    target_min = max(min_chunk_size, 320)
    # Ensure min chunk size is also multiple of 320
    if target_min % 320 != 0:
        target_min = ((target_min + 319) // 320) * 320

    chunks: List[bytes] = []
    total_len = len(pcm_bytes)
    offset = 0

    while offset < total_len:
        end = offset + chunk_size
        chunk = pcm_bytes[offset:end]

        # Check alignment / minimum size on final chunk
        if len(chunk) < target_min or len(chunk) % 320 != 0:
            target_chunk_len = max(target_min, ((len(chunk) + 319) // 320) * 320)
            pad_len = target_chunk_len - len(chunk)
            chunk = chunk + (b"\x00" * pad_len)

        chunks.append(chunk)
        offset = end

    return chunks


def calculate_pcm_energy(pcm_bytes: bytes) -> float:
    """Calculate Root Mean Square (RMS) energy of 16-bit signed PCM audio samples.

    Returns float RMS amplitude (0.0 to 32768.0).
    """
    if not pcm_bytes or len(pcm_bytes) < 2:
        return 0.0
    num_samples = len(pcm_bytes) // 2
    try:
        samples = struct.unpack(f"<{num_samples}h", pcm_bytes[: num_samples * 2])
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / num_samples)
    except Exception:
        return 0.0


def is_acoustic_chime_tone(pcm_bytes: bytes, sample_rate: int = 8000) -> bool:
    """Detect whether linear PCM audio contains synthetic acoustic chime notes or pure periodic prompt tone.

    Prevents telephony acoustic feedback loops where the caller's phone microphone or PSTN hybrid
    reflects the bot's own synthesized chime audio back into the inbound speech recognizer.
    """
    if not pcm_bytes or len(pcm_bytes) < 320:
        return False
    num_samples = len(pcm_bytes) // 2
    try:
        samples = struct.unpack(f"<{num_samples}h", pcm_bytes[: num_samples * 2])
    except Exception:
        return False

    # Analyze audio in windows of up to 1600 samples (200ms at 8kHz)
    window_size = min(num_samples, 1600)
    for start in range(0, num_samples - window_size + 1, window_size):
        w_samples = samples[start : start + window_size]
        var = sum(s * s for s in w_samples)
        if var == 0:
            continue
        rms = math.sqrt(var / len(w_samples))
        # Background noise below 150 RMS is not an active chime tone
        if rms < 150.0:
            continue

        # Check zero-crossing rate: chime chord notes (400Hz to 850Hz) have ZCR between 0.08 and 0.25 at 8kHz
        zc = sum(
            1
            for i in range(1, len(w_samples))
            if (w_samples[i - 1] >= 0 and w_samples[i] < 0) or (w_samples[i - 1] < 0 and w_samples[i] >= 0)
        )
        zcr = zc / len(w_samples)
        if 0.08 <= zcr <= 0.25:
            # Check strong periodic autocorrelation corresponding to chime note fundamental periods (lags 9 to 21)
            for lag in range(9, 21):
                if lag >= len(w_samples):
                    break
                corr = sum(w_samples[i] * w_samples[i - lag] for i in range(lag, len(w_samples)))
                norm_corr = corr / (var * ((len(w_samples) - lag) / len(w_samples)))
                if norm_corr > 0.75:
                    return True

    return False


class UtteranceDetector:
    """Voice Activity Detector and Speech Frame Accumulator for telephony audio streaming.

    Buffers continuous 16-bit linear PCM audio frames, handles pre-roll history to avoid clipping
    onsets, detects voice activity via RMS energy thresholding, and returns a complete audio
    utterance once trailing silence is observed or maximum utterance duration is reached.
    """

    def __init__(
        self,
        sample_rate: int = 8000,
        energy_threshold: float = 300.0,
        trailing_silence_seconds: float = 0.9,
        min_utterance_seconds: float = 0.5,
        max_utterance_seconds: float = 7.0,
        preroll_seconds: float = 0.3,
    ):
        self.sample_rate = sample_rate
        self.bytes_per_second = sample_rate * 2  # 16-bit mono = 2 bytes per sample
        self.energy_threshold = energy_threshold
        self.trailing_silence_seconds = trailing_silence_seconds
        self.min_utterance_seconds = min_utterance_seconds
        self.max_utterance_seconds = max_utterance_seconds
        self.preroll_max_bytes = int(preroll_seconds * self.bytes_per_second)

        self.is_speaking: bool = False
        self.speech_start_time: float = 0.0
        self.last_speech_time: float = 0.0
        self.consecutive_silent_bytes: int = 0
        self.last_speech_pcm_len: int = 0
        self.buffered_pcm: bytearray = bytearray()
        self.preroll_pcm: bytearray = bytearray()

    def reset(self) -> None:
        """Clear all buffered speech and reset voice activity state."""
        self.is_speaking = False
        self.speech_start_time = 0.0
        self.last_speech_time = 0.0
        self.consecutive_silent_bytes = 0
        self.last_speech_pcm_len = 0
        self.buffered_pcm.clear()
        self.preroll_pcm.clear()

    @property
    def buffered_duration(self) -> float:
        """Return the duration in seconds of currently buffered speech."""
        return len(self.buffered_pcm) / float(self.bytes_per_second)

    def process_chunk(self, chunk_pcm: bytes, now: float) -> Optional[bytes]:
        """Process an incoming 16-bit linear PCM audio chunk from the telephony stream.

        Args:
            chunk_pcm: Raw 16-bit mono PCM bytes (typically 20ms to 200ms).
            now: Current event loop timestamp (e.g. from asyncio.get_event_loop().time()).

        Returns:
            Complete utterance PCM bytes if speech ended or max duration was reached,
            otherwise None (indicating speech is still accumulating or line is silent).
        """
        if not chunk_pcm:
            return None

        energy = calculate_pcm_energy(chunk_pcm)
        is_active = energy >= self.energy_threshold

        if not self.is_speaking:
            if is_active:
                # Speech detected: start buffering speech and include pre-roll history
                self.is_speaking = True
                self.speech_start_time = now
                self.last_speech_time = now
                self.consecutive_silent_bytes = 0
                self.buffered_pcm = bytearray(self.preroll_pcm)
                self.preroll_pcm.clear()
                self.buffered_pcm.extend(chunk_pcm)
                self.last_speech_pcm_len = len(self.buffered_pcm)
                return None
            else:
                # Ambient silence before speech: update rolling pre-roll buffer
                self.preroll_pcm.extend(chunk_pcm)
                if len(self.preroll_pcm) > self.preroll_max_bytes:
                    self.preroll_pcm = self.preroll_pcm[-self.preroll_max_bytes:]
                return None
        else:
            # Speech already active: accumulate current chunk
            self.buffered_pcm.extend(chunk_pcm)
            if is_active:
                self.last_speech_time = now
                self.last_speech_pcm_len = len(self.buffered_pcm)
                self.consecutive_silent_bytes = 0
            else:
                self.consecutive_silent_bytes += len(chunk_pcm)

            audio_silence_sec = self.consecutive_silent_bytes / float(self.bytes_per_second)
            wall_silence_sec = (now - self.last_speech_time) if self.last_speech_time > 0 else 0.0
            silence_duration = max(audio_silence_sec, wall_silence_sec)

            total_duration = len(self.buffered_pcm) / float(self.bytes_per_second)
            speech_duration = self.last_speech_pcm_len / float(self.bytes_per_second)

            # End-of-utterance conditions:
            # 1. Trailing silence observed after speech
            # 2. Maximum utterance duration reached
            if silence_duration >= self.trailing_silence_seconds or total_duration >= self.max_utterance_seconds:
                if speech_duration >= self.min_utterance_seconds:
                    cushion_bytes = int(0.2 * self.bytes_per_second)
                    end_idx = min(len(self.buffered_pcm), self.last_speech_pcm_len + cushion_bytes)
                    complete_utterance = bytes(self.buffered_pcm[:end_idx])
                    self.reset()
                    return complete_utterance
                else:
                    # Noise burst or cough too short to be meaningful speech
                    self.reset()
                    return None

            return None



