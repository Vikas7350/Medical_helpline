from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.engine.conversation import conversation_manager
from app.engine.state_machine import ConversationState, TurnResult
from app.telephony.validator import TelephonyValidator


class TelephonyAdapter:
    """Telephony adapter translating incoming IVR webhooks to conversation turns."""

    @classmethod
    async def handle_webhook(
        cls,
        payload: Dict[str, Any],
        raw_body: bytes,
        signature: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Process incoming IVR webhook event."""
        # 1. Validate signature
        is_valid = TelephonyValidator.validate_webhook_signature(raw_body, signature)
        if not is_valid:
            logger.warning("Rejected telephony webhook with invalid signature")
            return {
                "status": "error",
                "message": "Invalid webhook signature",
                "action": "hangup",
            }

        call_sid = payload.get("CallSid") or payload.get("CallUUID") or payload.get("session_id")
        call_status = (payload.get("CallStatus") or "").lower()
        digits = payload.get("Digits") or payload.get("digits")
        speech_result = payload.get("SpeechResult") or payload.get("speech_result")
        caller_phone = payload.get("From")

        # Anonymize caller id - never store plain text phone
        anonymized_id = TelephonyValidator.anonymize_caller_id(caller_phone)
        logger.info(f"Telephony event: session={call_sid}, status={call_status}, caller_hash={anonymized_id}")

        # Handle disconnects / call completion
        if call_status in ("completed", "failed", "busy", "no-answer", "hangup"):
            if call_sid:
                conversation_manager.disconnect_call(session_id=call_sid, db=db)
            return {
                "status": "success",
                "session_id": call_sid,
                "action": "hangup",
                "message": "Call closed.",
            }

        # Initialize session or fetch active context
        ctx, initial_prompt = conversation_manager.get_or_create_context(session_id=call_sid, db=db)

        # Determine turn input: DTMF digits take precedence on keypad menus
        user_input = digits if digits is not None and str(digits).strip() != "" else speech_result
        is_dtmf = digits is not None and str(digits).strip() != ""

        # If incoming call just connected with no input yet
        if user_input is None or str(user_input).strip() == "":
            return {
                "status": "success",
                "session_id": ctx.session_id,
                "state": ctx.state.value,
                "spoken_text": initial_prompt,
                "gather_digits": True,
                "max_digits": 1,
                "action": "gather",
                "exotel_passthru": {
                    "action": "play_and_gather",
                    "prompt": initial_prompt,
                    "digits_allowed": "1,2,3,0,9",
                },
            }

        # Process conversation turn
        result: TurnResult = await conversation_manager.process_turn(
            session_id=ctx.session_id,
            caller_input=str(user_input),
            is_dtmf=is_dtmf,
            db=db,
        )

        response = {
            "status": "success",
            "session_id": ctx.session_id,
            "state": result.next_state.value,
            "spoken_text": result.spoken_text,
            "language": result.language,
            "is_completed": result.is_completed,
            "action": "hangup" if result.should_hangup else "gather",
            "gather_digits": result.requires_dtmf,
            "exotel_passthru": {
                "action": "hangup" if result.should_hangup else "play_and_record",
                "prompt": result.spoken_text,
            },
        }

        if result.triage_assessment:
            response["triage"] = {
                "urgency": result.triage_assessment.urgency_category,
                "is_emergency": result.triage_assessment.is_emergency,
                "referral_recommended": result.triage_assessment.referral_recommended,
            }

        return response
