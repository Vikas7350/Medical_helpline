import os
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load from .env if present
load_dotenv()


class Settings(BaseModel):
    """Application settings loaded from environment variables or .env file."""

    APP_NAME: str = "Multilingual AI Medical Helpline"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    DEBUG: bool = Field(default_factory=lambda: os.getenv("DEBUG", "true").lower() in ("true", "1", "yes"))

    # Server binding
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    # Database
    DATABASE_URL: str = Field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./helpline.db"))

    # Security
    ADMIN_API_KEY: str = Field(default_factory=lambda: os.getenv("ADMIN_API_KEY", "dev-hackathon-admin-key-2026"))
    ADMIN_SECRET_TOKEN: str = Field(default_factory=lambda: os.getenv("ADMIN_SECRET_TOKEN", "dev-secret-token-change-in-prod"))

    # Telephony configuration
    TELEPHONY_PROVIDER: str = Field(default_factory=lambda: os.getenv("TELEPHONY_PROVIDER", "mock"))
    EXOTEL_ACCOUNT_SID: str = Field(default_factory=lambda: os.getenv("EXOTEL_ACCOUNT_SID", ""))
    EXOTEL_API_KEY: str = Field(default_factory=lambda: os.getenv("EXOTEL_API_KEY", ""))
    EXOTEL_API_TOKEN: str = Field(default_factory=lambda: os.getenv("EXOTEL_API_TOKEN", ""))
    EXOTEL_VIRTUAL_NUMBER: str = Field(default_factory=lambda: os.getenv("EXOTEL_VIRTUAL_NUMBER", "+918000000000"))
    TELEPHONY_WEBHOOK_SECRET: str = Field(default_factory=lambda: os.getenv("TELEPHONY_WEBHOOK_SECRET", "dev_webhook_secret_key"))
    EXOTEL_STREAM_SAMPLE_RATE: int = Field(default_factory=lambda: int(os.getenv("EXOTEL_STREAM_SAMPLE_RATE", "8000")))
    EXOTEL_STREAM_BASE_URL: str = Field(default_factory=lambda: os.getenv("EXOTEL_STREAM_BASE_URL", ""))
    EXOTEL_STREAM_CHUNK_SIZE: int = Field(default_factory=lambda: int(os.getenv("EXOTEL_STREAM_CHUNK_SIZE", "3200")))
    EXOTEL_STREAM_REQUIRE_AUTH: bool = Field(default_factory=lambda: os.getenv("EXOTEL_STREAM_REQUIRE_AUTH", "false").lower() in ("true", "1", "yes"))

    # AI / Speech provider choices:
    # STT: "mock" | "speech_recognition" | "deepgram"
    # TTS: "mock" | "edge_tts" | "deepgram" | "openai"
    # LLM: "mock" | "grok" | "xai" | "openai" | "gemini"
    STT_PROVIDER: str = Field(default_factory=lambda: os.getenv("STT_PROVIDER", "mock"))
    TTS_PROVIDER: str = Field(default_factory=lambda: os.getenv("TTS_PROVIDER", "mock"))
    LLM_PROVIDER: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock"))

    XAI_API_KEY: str = Field(default_factory=lambda: os.getenv("XAI_API_KEY", ""))
    OPENAI_API_KEY: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    GEMINI_API_KEY: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    DEEPGRAM_API_KEY: str = Field(default_factory=lambda: os.getenv("DEEPGRAM_API_KEY", ""))

    # Privacy & Call Limits
    DATA_RETENTION_DAYS: int = Field(default_factory=lambda: int(os.getenv("DATA_RETENTION_DAYS", "90")))
    MAX_CALL_DURATION_SECONDS: int = Field(default_factory=lambda: int(os.getenv("MAX_CALL_DURATION_SECONDS", "480")))
    TURN_TIMEOUT_SECONDS: int = Field(default_factory=lambda: int(os.getenv("TURN_TIMEOUT_SECONDS", "30")))
    MAX_UNRECOGNIZED_TURNS: int = Field(default_factory=lambda: int(os.getenv("MAX_UNRECOGNIZED_TURNS", "3")))


settings = Settings()
