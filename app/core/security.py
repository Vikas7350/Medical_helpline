import hashlib
import hmac
import secrets
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings
from app.core.logging import logger

api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def verify_admin_access(
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> bool:
    """Validate admin authorization via X-Admin-API-Key header or Bearer token."""
    # Check API key header
    if api_key and secrets.compare_digest(api_key, settings.ADMIN_API_KEY):
        return True

    # Check Bearer token
    if bearer and bearer.credentials:
        if secrets.compare_digest(bearer.credentials, settings.ADMIN_SECRET_TOKEN) or \
           secrets.compare_digest(bearer.credentials, settings.ADMIN_API_KEY):
            return True

    logger.warning("Unauthorized access attempt to admin endpoint")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: valid admin API key or Bearer token required.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def verify_telephony_signature(
    raw_body: bytes,
    signature_header: Optional[str],
    secret_key: Optional[str] = None,
) -> bool:
    """Verify HMAC-SHA256 signature from IVR telephony webhook provider."""
    secret = (secret_key or settings.TELEPHONY_WEBHOOK_SECRET).encode("utf-8")

    # If in mock telephony mode and no signature provided, allow pass-through
    if settings.TELEPHONY_PROVIDER == "mock" and not signature_header:
        return True

    if not signature_header:
        return False

    computed_hmac = hmac.new(secret, raw_body, hashlib.sha256).hexdigest()
    return secrets.compare_digest(computed_hmac, signature_header)
