"""Handles Exotel Voicebot bidirectional real-time audio WebSocket streams."""

import asyncio
import base64
import json
import uuid
from datetime import datetime
from typing import Optional, Tuple
from fastapi import WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketState
from app.core.config import settings
from app.core.logging import logger
from app.engine.conversation import conversation_manager
from app.engine.state_machine import ConversationState
from app.services.stt import get_stt_service
from app.services.tts import get_tts_service
from app.telephony.audio import (
    calculate_pcm_energy,
    chunk_pcm_audio,
    is_acoustic_chime_tone,
    pcm_to_wav,
    wav_to_pcm,
    UtteranceDetector,
)

from app.telephony.validator import TelephonyValidator


def extract_stream_sid(message: dict) -> Optional[str]:
    """Extract Exotel stream_sid from message or start event payload across naming variations."""
    start = message.get("start") if isinstance(message.get("start"), dict) else {}
    return (
        message.get("stream_sid")
        or message.get("streamSid")
        or message.get("StreamSid")
        or message.get("stream_id")
        or message.get("streamId")
        or message.get("sid")
        or start.get("stream_sid")
        or start.get("streamSid")
        or start.get("StreamSid")
        or start.get("stream_id")
        or start.get("streamId")
        or start.get("sid")
    )


def extract_call_sid(message: dict) -> Optional[str]:
    """Extract Exotel call_sid from message or start event payload across naming variations."""
    start = message.get("start") if isinstance(message.get("start"), dict) else {}
    return (
        start.get("call_sid")
        or start.get("callSid")
        or start.get("CallSid")
        or start.get("call_id")
        or start.get("callId")
        or message.get("call_sid")
        or message.get("callSid")
        or message.get("CallSid")
        or message.get("call_id")
        or message.get("callId")
    )



class StreamSessionState:
    """Tracks sequence numbers, playback concurrency, utterance detection, and echo suppression state for an active Exotel stream."""

    def __init__(self, stream_sid: Optional[str] = None, sample_rate: int = 8000):
        self.stream_sid: Optional[str] = stream_sid
        self.sequence_counter: int = 0
        self.is_playing_audio: bool = False
        self.active_playback_task: Optional[asyncio.Task] = None
        self.stop_event: asyncio.Event = asyncio.Event()
        self.last_mark_sent: Optional[str] = None
        self.playback_finished_at: float = 0.0
        self.utterance_detector: UtteranceDetector = UtteranceDetector(sample_rate=sample_rate)
        self.post_prompt_silence_triggered: bool = False

    def next_seq(self) -> int:
        self.sequence_counter += 1
        return self.sequence_counter



class TelephonyStreamHandler:
    """Handles Exotel Voicebot bidirectional real-time audio WebSocket streaming protocol.

    Documentation:
    https://support.exotel.com/support/solutions/articles/3000108630-working-with-the-stream-and-voicebot-applet
    """

    @classmethod
    async def safe_send_text(
        cls,
        websocket: WebSocket,
        text_data: str,
        event_name: str = "message",
        stream_sid: Optional[str] = None,
    ) -> bool:
        """Safely send text message over WebSocket, catching and logging any send failure without leaking PII."""
        # 1. Validate connection state prior to sending
        if (
            websocket.client_state != WebSocketState.CONNECTED
            or websocket.application_state != WebSocketState.CONNECTED
        ):
            return False

        try:
            await websocket.send_text(text_data)
            return True
        except (WebSocketDisconnect, ConnectionResetError, BrokenPipeError) as conn_err:
            ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
            logger.info(
                f"[{ts}] WebSocket disconnected while sending {event_name} "
                f"(exception={type(conn_err).__name__}, stream_sid={stream_sid})"
            )
            return False
        except RuntimeError as rt_err:
            ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
            if "not connected" in str(rt_err).lower() or "accept" in str(rt_err).lower():
                logger.info(
                    f"[{ts}] WebSocket closed while sending {event_name} (stream_sid={stream_sid})"
                )
            else:
                logger.warning(
                    f"[{ts}] WebSocket send runtime error for {event_name}: {rt_err}"
                )
            return False
        except Exception as exc:
            ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
            logger.warning(
                f"[{ts}] WebSocket send error for {event_name} "
                f"(exception={type(exc).__name__}, message={str(exc)}, stream_sid={stream_sid})"
            )
            return False

    @classmethod
    async def send_audio_to_exotel(
        cls,
        websocket: WebSocket,
        audio_bytes: bytes,
        stream_sid: Optional[str] = None,
        chunk_size: Optional[int] = None,
        seq_start: int = 1,
        stop_event: Optional[asyncio.Event] = None,
        sample_rate: int = 8000,
        pace_stream: Optional[bool] = None,
        session_state: Optional[StreamSessionState] = None,
    ) -> Tuple[int, int, bool]:
        """Convert TTS audio to 16-bit linear PCM and stream in aligned chunks to Exotel.

        Chunk requirements from Exotel spec:
        - Minimum chunk size: 3.2k (3200 bytes, ~100ms at 16kHz or ~200ms at 8kHz).
        - Maximum chunk size: 100k.
        - Chunk size must be a multiple of 320 bytes.

        Returns (chunks_sent_count, next_sequence_number, is_completed).
        Stops immediately on disconnect, cancellation, or failed send.
        """
        fallback_next_seq = (session_state.sequence_counter + 1) if session_state else seq_start
        if not audio_bytes:
            return 0, fallback_next_seq, False

        if (
            websocket.client_state != WebSocketState.CONNECTED
            or websocket.application_state != WebSocketState.CONNECTED
        ):
            return 0, fallback_next_seq, False

        pcm_bytes = wav_to_pcm(audio_bytes)
        target_chunk_size = chunk_size or settings.EXOTEL_STREAM_CHUNK_SIZE
        chunks = chunk_pcm_audio(pcm_bytes, chunk_size=target_chunk_size)
        sent_count = 0

        # Mathematical pacing:
        # At 8kHz 16-bit mono PCM: 16,000 bytes/sec = 16 bytes/ms.
        # Each 3200-byte chunk represents 3200 / 16000 = 0.200s (200ms).
        # Live telephony streams chunks at real-time 1.0x playback rate.
        # Test environment runs with 0ms pacing for high-speed unit tests.
        should_pace = (settings.ENVIRONMENT != "test") if pace_stream is None else pace_stream

        for seq, chunk in enumerate(chunks):
            if stop_event and stop_event.is_set():
                ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
                logger.info(
                    f"[{ts}] [AUDIO_OUT] Audio streaming cancelled by stop event at chunk {seq + 1}/{len(chunks)} "
                    f"(stream_sid={stream_sid})"
                )
                break

            if (
                websocket.client_state != WebSocketState.CONNECTED
                or websocket.application_state != WebSocketState.CONNECTED
            ):
                break

            if session_state:
                current_seq = session_state.next_seq()
            else:
                current_seq = seq_start + seq

            payload_b64 = base64.b64encode(chunk).decode("ascii")
            msg = {
                "event": "media",
                "stream_sid": stream_sid,
                "media": {
                    "payload": payload_b64,
                },
            }

            success = await cls.safe_send_text(
                websocket=websocket,
                text_data=json.dumps(msg),
                event_name=f"media (chunk {seq + 1}/{len(chunks)})",
                stream_sid=stream_sid,
            )
            if not success:
                ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
                logger.info(
                    f"[{ts}] [AUDIO_OUT] Halting audio streaming after chunk {seq + 1}/{len(chunks)} "
                    f"due to send failure (stream_sid={stream_sid})"
                )
                break

            sent_count += 1
            ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
            logger.info(
                f"[{ts}] [AUDIO_OUT] Sent chunk {seq + 1}/{len(chunks)} "
                f"(bytes={len(chunk)}, stream_sid='{stream_sid}')"
            )

            # Exact real-time pacing: yield for chunk's playback duration before sending next
            if should_pace:
                chunk_duration_s = len(chunk) / float(sample_rate * 2)
                await asyncio.sleep(chunk_duration_s)
            else:
                await asyncio.sleep(0)

        final_seq = (session_state.sequence_counter + 1) if session_state else (seq_start + sent_count)
        is_completed = (sent_count == len(chunks)) and not (stop_event and stop_event.is_set())
        return sent_count, final_seq, is_completed

    @classmethod
    async def send_mark(
        cls,
        websocket: WebSocket,
        stream_sid: Optional[str],
        name: str,
        sequence_number: Optional[int] = None,
    ) -> bool:
        """Send Exotel mark event for playback synchronization."""
        if (
            websocket.client_state != WebSocketState.CONNECTED
            or websocket.application_state != WebSocketState.CONNECTED
        ):
            return False

        msg = {
            "event": "mark",
            "stream_sid": stream_sid,
            "mark": {"name": name},
        }
        ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        logger.info(
            f"[{ts}] [AUDIO_OUT_MARK] Outbound mark '{name}' sent (stream_sid={stream_sid})"
        )
        return await cls.safe_send_text(
            websocket=websocket,
            text_data=json.dumps(msg),
            event_name=f"mark ({name})",
            stream_sid=stream_sid,
        )

    @classmethod
    async def send_clear(
        cls,
        websocket: WebSocket,
        stream_sid: Optional[str],
    ) -> bool:
        """Send Exotel clear event to flush unplayed audio buffer on barge-in/interruption."""
        if (
            websocket.client_state != WebSocketState.CONNECTED
            or websocket.application_state != WebSocketState.CONNECTED
        ):
            return False

        msg = {
            "event": "clear",
            "stream_sid": stream_sid,
        }
        ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        logger.info(
            f"[{ts}] [AUDIO_OUT_CLEAR] Sent clear event to flush unplayed carrier audio buffer (stream_sid={stream_sid})"
        )
        return await cls.safe_send_text(
            websocket=websocket,
            text_data=json.dumps(msg),
            event_name="clear",
            stream_sid=stream_sid,
        )

    @classmethod
    async def handle_stream(
        cls,
        websocket: WebSocket,
        session_id: Optional[str] = None,
        sample_rate: Optional[int] = None,
        is_legacy_simulator: bool = False,
        db: Optional[Session] = None,
    ):
        # 1. Validate Exotel WebSocket Basic Authentication if configured
        auth_header = websocket.headers.get("authorization")
        is_authorized = TelephonyValidator.validate_websocket_auth(auth_header)
        if not is_authorized:
            logger.warning("Rejected Exotel WebSocket stream connection with invalid credentials")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await websocket.accept()

        stt = get_stt_service()
        tts = get_tts_service()

        # Session metadata extracted from connection or Exotel's 'start' event
        resolved_session_id = session_id or websocket.query_params.get("session_id") or websocket.query_params.get("CallSid")
        query_stream_sid = (
            websocket.query_params.get("stream_sid")
            or websocket.query_params.get("streamSid")
            or websocket.query_params.get("StreamSid")
            or websocket.query_params.get("stream_id")
            or websocket.query_params.get("streamId")
        )
        current_sample_rate = sample_rate or settings.EXOTEL_STREAM_SAMPLE_RATE
        is_exotel_protocol = False
        ctx = None

        # State tracker managing monotonic sequence numbers, playback concurrency, utterance detection, and echo suppression
        state = StreamSessionState(stream_sid=query_stream_sid, sample_rate=current_sample_rate)

        ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        logger.info(
            f"[{ts}] [CALL_CONNECT] WebSocket telephony stream accepted "
            f"(session_id={resolved_session_id}, stream_sid='{state.stream_sid}', simulator={is_legacy_simulator})"
        )

        # Helper coroutine to halt active playback without blocking
        async def stop_playback():
            state.stop_event.set()
            if state.active_playback_task and not state.active_playback_task.done():
                state.active_playback_task.cancel()
                try:
                    await state.active_playback_task
                except (asyncio.CancelledError, Exception):
                    pass
            state.active_playback_task = None
            state.stop_event = asyncio.Event()
            state.is_playing_audio = False
            state.playback_finished_at = asyncio.get_event_loop().time()
            state.utterance_detector.reset()

        # Playback worker streaming chunks concurrently while main loop receives events
        async def play_audio_worker(audio_bytes: bytes, mark_name: str, target_sr: int):
            try:
                sent, next_seq, is_completed = await cls.send_audio_to_exotel(
                    websocket=websocket,
                    audio_bytes=audio_bytes,
                    stream_sid=state.stream_sid,
                    stop_event=state.stop_event,
                    sample_rate=target_sr,
                    session_state=state,
                )
                # ONLY send mark if all chunks successfully completed without interruption or disconnect
                if is_completed and not state.stop_event.is_set() and websocket.client_state == WebSocketState.CONNECTED:
                    await cls.send_mark(
                        websocket=websocket,
                        stream_sid=state.stream_sid,
                        name=mark_name,
                    )
                    state.last_mark_sent = mark_name
                    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
                    logger.info(
                        f"[{ts}] [AUDIO_OUT_MARK] Outbound playback completed, mark sent: name='{mark_name}', "
                        f"stream_sid='{state.stream_sid}'"
                    )
            finally:
                state.is_playing_audio = False
                state.playback_finished_at = asyncio.get_event_loop().time()

        async def start_playback(audio_bytes: bytes, mark_name: str):
            await stop_playback()
            state.is_playing_audio = True
            state.post_prompt_silence_triggered = False
            state.utterance_detector.reset()
            pcm_bytes = wav_to_pcm(audio_bytes)
            target_chunk_size = settings.EXOTEL_STREAM_CHUNK_SIZE
            chunks = chunk_pcm_audio(pcm_bytes, chunk_size=target_chunk_size)
            ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
            logger.info(
                f"[{ts}] [AUDIO_OUT_START] Outbound audio playback initiated: name='{mark_name}', "
                f"total_chunks={len(chunks)}, duration_ms={int(len(pcm_bytes) / 16)}ms, "
                f"stream_sid='{state.stream_sid}'"
            )
            state.active_playback_task = asyncio.create_task(
                play_audio_worker(audio_bytes, mark_name, current_sample_rate)
            )


        # Only deliver initial mock greeting text event if explicitly operating in legacy simulation mode
        if is_legacy_simulator and resolved_session_id:
            ctx, initial_prompt = conversation_manager.get_or_create_context(session_id=resolved_session_id, db=db)
            await cls.safe_send_text(
                websocket=websocket,
                text_data=json.dumps({
                    "event": "greeting",
                    "text": initial_prompt,
                    "session_id": resolved_session_id,
                }),
                event_name="mock_greeting",
                stream_sid=state.stream_sid,
            )

        try:
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                event_type = message.get("event")

                # A. Exotel 'connected' event
                if event_type == "connected":
                    is_exotel_protocol = True
                    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
                    logger.info(f"[{ts}] Exotel WebSocket connected event received")
                    continue

                # B. Exotel 'start' event (contains stream_sid, call_sid, media format)
                elif event_type == "start":
                    is_exotel_protocol = True
                    start_data = message.get("start") if isinstance(message.get("start"), dict) else {}
                    extracted_sid = extract_stream_sid(message)
                    if extracted_sid:
                        state.stream_sid = extracted_sid

                    extracted_call_sid = extract_call_sid(message)
                    if extracted_call_sid:
                        resolved_session_id = extracted_call_sid

                    media_fmt = start_data.get("media_format") if isinstance(start_data.get("media_format"), dict) else {}
                    if media_fmt.get("sample_rate"):
                        try:
                            current_sample_rate = int(media_fmt.get("sample_rate"))
                        except (ValueError, TypeError):
                            pass

                    caller_phone = start_data.get("from")
                    caller_hash = TelephonyValidator.anonymize_caller_id(caller_phone)
                    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
                    logger.info(
                        f"[{ts}] [CALL_START] Exotel stream started: stream_sid={state.stream_sid}, "
                        f"session={resolved_session_id}, caller_hash={caller_hash}, sample_rate={current_sample_rate}"
                    )

                    if not resolved_session_id:
                        resolved_session_id = str(uuid.uuid4())

                    ctx, initial_prompt = conversation_manager.get_or_create_context(session_id=resolved_session_id, db=db)
                    try:
                        greeting_audio = await tts.synthesize(initial_prompt, language=ctx.language or "en")
                        # Launch concurrent audio playback task; receive loop stays active
                        await start_playback(greeting_audio, "greeting")
                    except Exception as tts_err:
                        logger.error(f"[AUDIO_OUT] Speech generation failed for initial greeting: {tts_err}")

                # C. Exotel 'dtmf' event (caller pressed keypad digit)
                elif event_type == "dtmf":
                    if not resolved_session_id:
                        resolved_session_id = str(uuid.uuid4())
                        ctx, _ = conversation_manager.get_or_create_context(session_id=resolved_session_id, db=db)

                    dtmf_data = message.get("dtmf") or {}
                    digit = dtmf_data.get("digit") if isinstance(dtmf_data, dict) else dtmf_data
                    if not digit:
                        digit = message.get("digit", "")
                    digit_str = str(digit).strip()
                    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]

                    logger.info(
                        f"[{ts}] [AUDIO_IN] Telephony DTMF received: digit='{digit_str}' for session {resolved_session_id}"
                    )

                    # Stop active audio streaming immediately (barge-in) and send clear event
                    await stop_playback()

                    if state.stream_sid:
                        await cls.send_clear(websocket, stream_sid=state.stream_sid)

                    prev_state = ctx.state if ctx else ConversationState.LANGUAGE_SELECT
                    turn_res = await conversation_manager.process_turn(
                        session_id=resolved_session_id,
                        caller_input=digit_str,
                        is_dtmf=True,
                        db=db,
                    )

                    logger.info(
                        f"[{ts}] [STATE_CHANGE] Session {resolved_session_id}: {prev_state.value} -> "
                        f"{turn_res.next_state.value} (input='{digit_str}', dtmf=True, lang={turn_res.language})"
                    )

                    # Mock mode text event for legacy test clients / simulator
                    if not is_exotel_protocol:
                        await cls.safe_send_text(
                            websocket=websocket,
                            text_data=json.dumps({
                                "event": "response",
                                "text": turn_res.spoken_text,
                                "is_completed": turn_res.is_completed,
                            }),
                            event_name="mock_response",
                            stream_sid=state.stream_sid,
                        )

                    # Synthesize and stream audio response concurrently
                    try:
                        resp_audio = await tts.synthesize(turn_res.spoken_text, language=turn_res.language)
                        turn_mark = f"turn_{ctx.turns_count if ctx else 1}"
                        await start_playback(resp_audio, turn_mark)
                    except Exception as tts_err:
                        logger.error(f"[AUDIO_OUT] Speech generation failed for DTMF turn response: {tts_err}")

                    if turn_res.is_completed or turn_res.should_hangup:
                        logger.info(
                            f"[{ts}] [STATE_CHANGE] Conversation completed for session {resolved_session_id}; closing stream"
                        )
                        if state.active_playback_task:
                            await state.active_playback_task
                        await websocket.close()
                        break

                # D. Exotel 'media' event (inbound audio chunk from caller)
                elif event_type == "media":
                    if not resolved_session_id:
                        resolved_session_id = str(uuid.uuid4())
                        ctx, _ = conversation_manager.get_or_create_context(session_id=resolved_session_id, db=db)

                    media_info = message.get("media", {})
                    payload_base64 = media_info.get("payload", "") if isinstance(media_info, dict) else ""
                    if not payload_base64:
                        continue

                    # Base64 decode raw audio payload
                    try:
                        raw_bytes = base64.b64decode(payload_base64)
                    except Exception:
                        raw_bytes = payload_base64.encode("utf-8")

                    is_plain_text = False
                    transcription = ""
                    try:
                        if len(raw_bytes) < 500:
                            decoded_text = raw_bytes.decode("utf-8").strip()
                            if decoded_text and decoded_text.isprintable() and not raw_bytes.startswith(b"RIFF"):
                                transcription = decoded_text
                                is_plain_text = True
                    except Exception:
                        pass

                    now = asyncio.get_event_loop().time()
                    audio_energy = calculate_pcm_energy(raw_bytes) if not is_plain_text else 500.0
                    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]

                    # 1. Echo suppression: Gating during active outbound streaming & line settling grace period
                    # In full-duplex telephony without echo suppression, outbound chime/prompts echo back as inbound audio.
                    settling_time = 0.0 if settings.ENVIRONMENT == "test" else 0.35
                    is_in_echo_window = state.is_playing_audio or (now - state.playback_finished_at < settling_time)
                    if is_in_echo_window and not is_plain_text:
                        state.utterance_detector.reset()
                        logger.debug(
                            f"[{ts}] [AUDIO_IN] Echo suppressed: chunk ignored during outbound audio playout "
                            f"(bytes={len(raw_bytes)}, RMS={audio_energy:.1f}, stream_sid={state.stream_sid})"
                        )
                        continue

                    if not is_plain_text:
                        was_speaking = state.utterance_detector.is_speaking
                        utterance_pcm = state.utterance_detector.process_chunk(raw_bytes, now=now)

                        # Log speech start
                        if not was_speaking and state.utterance_detector.is_speaking:
                            logger.info(
                                f"[{ts}] [VAD] Caller started speaking: RMS={audio_energy:.1f}, session={resolved_session_id}"
                            )

                        # Check for post-prompt silence timeout (caller silent for >= 7.0s after prompt finished)
                        time_since_playback = now - state.playback_finished_at
                        if (
                            utterance_pcm is None
                            and not state.utterance_detector.is_speaking
                            and state.playback_finished_at > 0
                            and time_since_playback >= 7.0
                            and not state.post_prompt_silence_triggered
                        ):
                            state.post_prompt_silence_triggered = True
                            logger.info(
                                f"[{ts}] [AUDIO_IN] Post-prompt silence timeout ({time_since_playback:.1f}s). "
                                f"Triggering silence re-prompt for session {resolved_session_id}."
                            )
                            transcription = ""
                        elif utterance_pcm is None:
                            # Audio chunk buffered into utterance detector, or pre-speech silence
                            continue
                        else:
                            # Complete utterance detected and ready for STT
                            if is_acoustic_chime_tone(utterance_pcm):
                                logger.info(
                                    f"[{ts}] [AUDIO_IN] Discarded acoustic chime reflection "
                                    f"(RMS={calculate_pcm_energy(utterance_pcm):.1f}, bytes={len(utterance_pcm)})"
                                )
                                continue

                            utterance_dur = len(utterance_pcm) / float(current_sample_rate * 2)
                            target_lang = (ctx.language if ctx else None) or "en"
                            logger.info(
                                f"[{ts}] [AUDIO_IN] Utterance complete ({utterance_dur:.2f}s, {len(utterance_pcm)} bytes, "
                                f"lang='{target_lang}', session={resolved_session_id}). Transcribing..."
                            )

                            wav_data = pcm_to_wav(utterance_pcm, sample_rate=current_sample_rate)
                            transcription = await stt.transcribe(wav_data, language=target_lang)

                            logger.info(
                                f"[{ts}] [STT_OUT] Transcript: '{transcription}' "
                                f"(len={len(transcription)}, lang='{target_lang}', session={resolved_session_id})"
                            )

                    # 3. State-aware filtering: In LANGUAGE_SELECT state, the IVR waits for DTMF (1/2/3) or language choice.
                    # Ignore general speech/noise that doesn't correspond to a language selection, avoiding false retry counts.
                    if ctx and ctx.state == ConversationState.LANGUAGE_SELECT:
                        norm_input = transcription.lower().strip()
                        valid_lang_keywords = {
                            "1", "en", "english",
                            "2", "hi", "hindi", "हिंदी",
                            "3", "mr", "marathi", "मराठी",
                        }
                        if not any(k in norm_input for k in valid_lang_keywords):
                            logger.info(
                                f"[{ts}] [AUDIO_IN] Ignoring non-language input in LANGUAGE_SELECT state "
                                f"(transcript='{transcription}'). Awaiting DTMF (1, 2, 3) or spoken language choice."
                            )
                            continue

                    # If in LANGUAGE_SELECT and transcription is empty, do nothing
                    if not transcription and ctx and ctx.state == ConversationState.LANGUAGE_SELECT:
                        continue

                    # 4. Valid caller speech received (or silence timeout): halt any playing audio (barge-in) and flush carrier buffer
                    await stop_playback()
                    if state.stream_sid:
                        await cls.send_clear(websocket, stream_sid=state.stream_sid)

                    prev_state = ctx.state if ctx else ConversationState.LANGUAGE_SELECT
                    turn_res = await conversation_manager.process_turn(
                        session_id=resolved_session_id,
                        caller_input=transcription,
                        is_dtmf=False,
                        db=db,
                    )


                    logger.info(
                        f"[{ts}] [STATE_CHANGE] Session {resolved_session_id}: {prev_state.value} -> "
                        f"{turn_res.next_state.value} (input='{transcription[:25]}...', dtmf=False, lang={turn_res.language})"
                    )

                    if not is_exotel_protocol:
                        await cls.safe_send_text(
                            websocket=websocket,
                            text_data=json.dumps({
                                "event": "response",
                                "text": turn_res.spoken_text,
                                "is_completed": turn_res.is_completed,
                            }),
                            event_name="mock_response",
                            stream_sid=state.stream_sid,
                        )

                    try:
                        resp_audio = await tts.synthesize(turn_res.spoken_text, language=turn_res.language)
                        turn_mark = f"turn_{ctx.turns_count if ctx else 1}"
                        await start_playback(resp_audio, turn_mark)
                    except Exception as tts_err:
                        logger.error(f"[AUDIO_OUT] Speech generation failed for speech turn response: {tts_err}")

                    if turn_res.is_completed or turn_res.should_hangup:
                        logger.info(
                            f"[{ts}] [STATE_CHANGE] Conversation completed for session {resolved_session_id}; closing stream"
                        )
                        if state.active_playback_task:
                            await state.active_playback_task
                        await websocket.close()
                        break

                # E. Exotel 'mark' event (playback completed acknowledgment from carrier)
                elif event_type == "mark":
                    mark_name = message.get("mark", {}).get("name", "")
                    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
                    logger.info(
                        f"[{ts}] [AUDIO_MARK_ACK] Exotel mark acknowledged: '{mark_name}' for session {resolved_session_id}"
                    )
                    state.playback_finished_at = asyncio.get_event_loop().time()

                # F. Exotel 'clear' event
                elif event_type == "clear":
                    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
                    logger.info(f"[{ts}] [AUDIO_CLEAR_ACK] Exotel clear acknowledged for session {resolved_session_id}")

                # G. Exotel 'stop' event (stream stopped / call hung up)
                elif event_type == "stop":
                    ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
                    logger.info(f"[{ts}] [STOP_EVENT_RAW] Raw stop event JSON from Exotel: {data}")

                    stop_data = message.get("stop")
                    raw_stop_reason = None
                    if isinstance(stop_data, dict):
                        raw_stop_reason = stop_data.get("reason")
                    elif isinstance(stop_data, str):
                        raw_stop_reason = stop_data

                    top_level_reason = message.get("reason")
                    exact_reason = raw_stop_reason if raw_stop_reason is not None else (top_level_reason if top_level_reason is not None else "unspecified")
                    normalized_reason = str(exact_reason).strip()

                    logger.info(
                        f"[{ts}] [DISCONNECT] Exotel sent 'stop' event: stop.reason='{normalized_reason}', "
                        f"stream_sid='{state.stream_sid}', session={resolved_session_id}, "
                        f"chunks_sent_total={state.sequence_counter}, is_playing={state.is_playing_audio}"
                    )
                    await stop_playback()
                    break

        except WebSocketDisconnect as ws_disc:
            await stop_playback()
            ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
            logger.info(
                f"[{ts}] [DISCONNECT] Exotel closed WebSocket connection directly: "
                f"close_code={ws_disc.code}, stream_sid='{state.stream_sid}' for session {resolved_session_id}"
            )
        except RuntimeError as rt_err:
            await stop_playback()
            ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
            if "not connected" in str(rt_err).lower() or "accept" in str(rt_err).lower():
                logger.info(
                    f"[{ts}] [DISCONNECT] Exotel WebSocket closed by remote host for session {resolved_session_id}"
                )
            else:
                logger.warning(
                    f"[{ts}] WebSocket runtime error for session {resolved_session_id}: {rt_err}"
                )
        except Exception as e:
            await stop_playback()
            ts = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
            logger.error(
                f"[{ts}] WebSocket streaming error for session {resolved_session_id}: {type(e).__name__}: {e}"
            )
        finally:
            await stop_playback()
            if resolved_session_id:
                conversation_manager.disconnect_call(session_id=resolved_session_id, db=db)
