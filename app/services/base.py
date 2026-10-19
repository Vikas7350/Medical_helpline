from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseSTTService(ABC):
    """Abstract interface for Speech-to-Text transcription."""

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> str:
        """Transcribe speech audio into text."""
        pass


class BaseTTSService(ABC):
    """Abstract interface for Text-to-Speech synthesis."""

    @abstractmethod
    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """Synthesize text into playable audio bytes (WAV/MP3)."""
        pass


class BaseLLMService(ABC):
    """Abstract interface for Language Model guidance generation."""

    @abstractmethod
    async def generate_guidance(
        self,
        symptom_text: str,
        language: str = "en",
        triage_guidance: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate empathetic spoken guidance incorporating triage results."""
        pass
