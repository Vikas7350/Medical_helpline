import logging
import re
import sys
from typing import Any, Dict


PHONE_PATTERN = re.compile(r"(\+?91[\-\s]?)?[6-9]\d{9}")
EMAIL_PATTERN = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
BASIC_AUTH_PATTERN = re.compile(r"Basic\s+[A-Za-z0-9+/=]+", re.IGNORECASE)
BEARER_TOKEN_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]+", re.IGNORECASE)
URL_CREDENTIALS_PATTERN = re.compile(r"([a-zA-Z]+://)([^:\s/@]+):([^@\s/]+)@")
CREDENTIAL_KEY_PATTERN = re.compile(
    r"(?i)(api[_-]?key|api[_-]?token|secret[_-]?token|webhook[_-]?secret|password|auth_token)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{4,})['\"]?"
)


class SanitizingFormatter(logging.Formatter):
    """Logging formatter that redacts credentials, telephone numbers, and emails to guarantee privacy."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        # Redact credentials & authorization tokens
        msg = BASIC_AUTH_PATTERN.sub("Basic [REDACTED_CREDENTIAL]", msg)
        msg = BEARER_TOKEN_PATTERN.sub("Bearer [REDACTED_CREDENTIAL]", msg)
        msg = URL_CREDENTIALS_PATTERN.sub(r"\1[REDACTED_USER]:[REDACTED_PASS]@", msg)
        msg = CREDENTIAL_KEY_PATTERN.sub(r"\1=[REDACTED]", msg)

        # Redact potential telephone numbers and emails
        msg = PHONE_PATTERN.sub("[REDACTED_PHONE]", msg)
        msg = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", msg)
        return msg


def setup_logging(debug: bool = False) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO

    logger = logging.getLogger("helpline")
    logger.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = SanitizingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logging()
