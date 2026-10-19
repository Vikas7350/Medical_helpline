import hashlib
import hmac
from typing import Optional
from app.core.config import settings
from app.core.logging import logger


class TelephonyValidator:
    """Validates incoming telephony webhook requests and hashes phone numbers for privacy."""

    @staticmethod
    def anonymize_caller_id(raw_phone: Optional[str]) -> str:
        """Create a non-reversible cryptographic hash of the phone number for session correlation only."""
        if not raw_phone:
            return "ANONYMOUS_CALLER"
        return hashlib.sha256(raw_phone.strip().encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def validate_webhook_signature(
        raw_body: bytes,
        signature: Optional[str],
        secret: Optional[str] = None,
    ) -> bool:
        if settings.TELEPHONY_PROVIDER == "mock" and not signature:
            return True

        if not signature:
            return False

        secret_key = (secret or settings.TELEPHONY_WEBHOOK_SECRET).encode("utf-8")
        expected_sig = hmac.new(secret_key, raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)

    @staticmethod
    def validate_websocket_auth(
        authorization_header: Optional[str],
        api_key: Optional[str] = None,
        api_token: Optional[str] = None,
    ) -> bool:
        """Validate Exotel Basic Authentication header on WebSocket handshake.

        Exotel format: 'Authorization: Basic base64(API_KEY:API_TOKEN)'
        Allows unauthenticated access when running in mock mode or when credentials are not configured.
        """
        if settings.TELEPHONY_PROVIDER == "mock":
            return True

        expected_key = api_key or settings.EXOTEL_API_KEY
        expected_token = api_token or settings.EXOTEL_API_TOKEN

        # Check if production credentials are configured
        has_configured_creds = (
            bool(expected_key)
            and bool(expected_token)
            and expected_key != "your_exotel_api_key_here"
            and expected_token != "your_exotel_api_token_here"
        )

        # 1. No Authorization header sent by Exotel:
        # Exotel uses IP Whitelisting by default unless Basic Auth credentials are in the applet URL.
        if not authorization_header:
            if settings.EXOTEL_STREAM_REQUIRE_AUTH and has_configured_creds:
                return False
            # Allow IP whitelisting mode
            return True

        # 2. Authorization header IS present: validate Basic Auth
        if not authorization_header.startswith("Basic "):
            return False

        if not has_configured_creds:
            return True

        try:
            import base64
            encoded_creds = authorization_header[6:].strip()
            decoded = base64.b64decode(encoded_creds).decode("utf-8")
            if ":" not in decoded:
                return False
            user, password = decoded.split(":", 1)
            return hmac.compare_digest(user, expected_key) and hmac.compare_digest(password, expected_token)
        except Exception:
            return False

