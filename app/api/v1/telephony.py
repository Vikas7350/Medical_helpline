from typing import Any, Dict, Optional
from fastapi import APIRouter, Header, Query, Request, WebSocket, status
from sqlalchemy.orm import Session
from app.api.deps import DatabaseSession
from app.core.config import settings
from app.telephony.adapter import TelephonyAdapter
from app.telephony.websocket_stream import TelephonyStreamHandler

router = APIRouter(prefix="/telephony", tags=["Telephony Integration"])


@router.post("/webhook")
async def telephony_webhook(
    request: Request,
    x_exotel_signature: Optional[str] = Header(None),
    x_telephony_signature: Optional[str] = Header(None),
    db: Session = DatabaseSession,
):
    """Receive and process validated telephony IVR events (Exotel or Generic IVR)."""
    raw_body = await request.body()
    signature = x_exotel_signature or x_telephony_signature

    payload: Dict[str, Any] = {}
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
    else:
        # Form-urlencoded data standard in telephony webhooks
        try:
            form = await request.form()
            payload = dict(form)
        except Exception:
            payload = {}

    response = await TelephonyAdapter.handle_webhook(
        payload=payload,
        raw_body=raw_body,
        signature=signature,
        db=db,
    )

    return response


@router.api_route("/voicebot", methods=["GET", "POST"])
async def exotel_voicebot_dynamic_endpoint(
    request: Request,
    sample_rate: Optional[int] = Query(None, alias="sample-rate"),
):
    """Exotel Voicebot Applet Dynamic URL Endpoint.

    When Exotel Voicebot Applet is configured with an HTTPS URL, Exotel queries this endpoint
    and expects a JSON response containing the target 'url' for WebSocket streaming:
    {"url": "wss://streamhandler.yourdomain.com?sample-rate=8000"}

    Documentation:
    https://support.exotel.com/support/solutions/articles/3000108630-working-with-the-stream-and-voicebot-applet
    """
    effective_sample_rate = sample_rate or settings.EXOTEL_STREAM_SAMPLE_RATE

    # Parse call SID if provided in query or form
    call_sid = request.query_params.get("CallSid") or request.query_params.get("session_id")
    if not call_sid and request.method == "POST":
        try:
            form = await request.form()
            call_sid = form.get("CallSid") or form.get("session_id")
        except Exception:
            pass

    # Build WebSocket URL
    if settings.EXOTEL_STREAM_BASE_URL:
        base_ws = settings.EXOTEL_STREAM_BASE_URL.rstrip("/")
    else:
        # Infer from current request (supporting reverse proxies and forwarded headers)
        forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
        ws_scheme = "wss" if (request.url.scheme == "https" or forwarded_proto == "https") else "ws"
        host = request.headers.get("x-forwarded-host") or request.url.netloc
        base_ws = f"{ws_scheme}://{host}/api/v1/telephony/stream"

    # Append query params
    params = [f"sample-rate={effective_sample_rate}"]
    if call_sid:
        params.append(f"session_id={call_sid}")

    delimiter = "&" if "?" in base_ws else "?"
    final_ws_url = f"{base_ws}{delimiter}{'&'.join(params)}"

    return {"url": final_ws_url}


@router.websocket("/stream")
async def telephony_audio_stream_direct(
    websocket: WebSocket,
    sample_rate: Optional[int] = Query(None, alias="sample-rate"),
    session_id: Optional[str] = Query(None),
    db: Session = DatabaseSession,
):
    """Exotel Voicebot Bidirectional Audio WebSocket Stream (Direct endpoint).

    Supports Exotel's Voicebot Applet connection where session_id and parameters
    are dynamically delivered in Exotel's 'start' event or query parameters.
    """
    await TelephonyStreamHandler.handle_stream(
        websocket=websocket,
        session_id=session_id,
        sample_rate=sample_rate,
        is_legacy_simulator=False,
        db=db,
    )


@router.websocket("/stream/{session_id}")
async def telephony_audio_stream_with_session(
    websocket: WebSocket,
    session_id: str,
    sample_rate: Optional[int] = Query(None, alias="sample-rate"),
    db: Session = DatabaseSession,
):
    """Exotel Voicebot Bidirectional Audio WebSocket Stream (Path-parameter endpoint).

    Supports path-based session routing for backward compatibility with mock simulator.
    """
    await TelephonyStreamHandler.handle_stream(
        websocket=websocket,
        session_id=session_id,
        sample_rate=sample_rate,
        is_legacy_simulator=(sample_rate is None),
        db=db,
    )
