"""Conversation coordinator managing active call sessions and database sync."""

import uuid
from datetime import datetime
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import logger
from app.database.models import round_to_minute
from app.database.repository import SessionRepository
from app.engine.localization import WELCOME_IVR_MENU, get_prompt
from app.engine.state_machine import (
    ConversationContext,
    ConversationState,
    HelplineStateMachine,
    TurnResult,
)
from app.services.tts import get_tts_service



class ConversationManager:
    """Manages active helpline call sessions, state transitions, and anonymous DB logging."""

    def __init__(self):
        # In-memory session pool for fast telephony turn-by-turn routing
        self._active_sessions: Dict[str, ConversationContext] = {}

    def get_or_create_context(
        self,
        session_id: Optional[str] = None,
        is_synthetic: bool = False,
        db: Optional[Session] = None,
    ) -> Tuple[ConversationContext, str]:
        s_id = session_id or str(uuid.uuid4())

        if s_id in self._active_sessions:
            ctx = self._active_sessions[s_id]
            return ctx, ctx.last_spoken_prompt

        ctx = ConversationContext(
            session_id=s_id,
            state=ConversationState.LANGUAGE_SELECT,
            last_spoken_prompt=WELCOME_IVR_MENU,
            is_synthetic=is_synthetic,
        )
        self._active_sessions[s_id] = ctx

        # Sync anonymous record to DB if db session provided
        if db:
            try:
                SessionRepository.create_session(
                    db=db,
                    session_id=s_id,
                    language=None,
                    is_synthetic=is_synthetic,
                )
            except Exception as e:
                logger.error(f"Error persisting session {s_id} to DB: {e}")

        return ctx, WELCOME_IVR_MENU

    def get_context(self, session_id: str) -> Optional[ConversationContext]:
        return self._active_sessions.get(session_id)

    async def select_language(
        self,
        session_id: str,
        language_or_digit: str,
        db: Optional[Session] = None,
    ) -> TurnResult:
        ctx, _ = self.get_or_create_context(session_id=session_id, db=db)
        result = HelplineStateMachine.process_turn(ctx, caller_input=language_or_digit, is_dtmf=True)

        if db and ctx.language:
            SessionRepository.update_session(db, session_id=session_id, selected_language=ctx.language)

        return result

    async def process_turn(
        self,
        session_id: str,
        caller_input: str,
        is_dtmf: bool = False,
        db: Optional[Session] = None,
    ) -> TurnResult:
        ctx, _ = self.get_or_create_context(session_id=session_id, db=db)

        # Check call duration limit
        duration_so_far = (datetime.utcnow() - ctx.created_at).total_seconds()
        if duration_so_far > settings.MAX_CALL_DURATION_SECONDS:
            ctx.state = ConversationState.COMPLETED
            ctx.is_completed = True
            lang = ctx.language or "en"
            timeout_msg = f"{WELCOME_IVR_MENU if not ctx.language else ''} Call timed out. Goodbye."
            result = TurnResult(
                next_state=ConversationState.COMPLETED,
                spoken_text=timeout_msg,
                language=lang,
                is_completed=True,
                should_hangup=True,
                requires_dtmf=False,
                triage_assessment=ctx.triage_assessment,
            )
            self._sync_to_db(ctx, db)
            return result

        result = HelplineStateMachine.process_turn(ctx, caller_input=caller_input, is_dtmf=is_dtmf)

        # Enrich spoken guidance with configured LLM when transitioning to GUIDANCE_DELIVERED
        if (
            result.next_state == ConversationState.GUIDANCE_DELIVERED
            and not ctx.is_synthetic
            and settings.LLM_PROVIDER.lower() in ("grok", "xai", "openai")
        ):
            try:
                from app.services.llm import get_llm_service

                llm_service = get_llm_service()
                symptom_summary = ctx.symptoms_text or caller_input
                llm_guidance = await llm_service.generate_guidance(
                    symptom_text=symptom_summary,
                    language=result.language,
                    triage_guidance=ctx.triage_assessment.guidance_text if ctx.triage_assessment else None,
                )
                if llm_guidance:
                    repeat_inst = get_prompt("repeat_instruction", result.language)
                    result.spoken_text = f"{llm_guidance} {repeat_inst}".strip()
                    ctx.last_spoken_prompt = result.spoken_text
            except Exception as llm_err:
                logger.warning(f"Error enriching guidance with {settings.LLM_PROVIDER} LLM: {llm_err}")

        # Sync to DB
        self._sync_to_db(ctx, db)
        return result


    def disconnect_call(self, session_id: str, db: Optional[Session] = None) -> None:
        """Handle disconnected/dropped call gracefully."""
        ctx = self._active_sessions.get(session_id)
        if ctx:
            ctx.state = ConversationState.DISCONNECTED
            self._sync_to_db(ctx, db)
            # Remove from active memory after marking completed/disconnected
            self._active_sessions.pop(session_id, None)

    def _sync_to_db(self, ctx: ConversationContext, db: Optional[Session]) -> None:
        if not db:
            return
        try:
            updates = {
                "selected_language": ctx.language,
                "turns_count": ctx.turns_count,
                "duration_seconds": int((datetime.utcnow() - ctx.created_at).total_seconds()),
                "is_completed": ctx.is_completed,
            }
            if ctx.triage_assessment:
                updates["symptom_category"] = ctx.triage_assessment.symptom_category
                updates["urgency_category"] = ctx.triage_assessment.urgency_category
                updates["referral_recommended"] = ctx.triage_assessment.referral_recommended

            if ctx.is_completed or ctx.state in (ConversationState.COMPLETED, ConversationState.DISCONNECTED):
                updates["completed_at"] = round_to_minute()

            SessionRepository.update_session(db, session_id=ctx.session_id, **updates)
        except Exception as e:
            logger.error(f"Failed to sync session {ctx.session_id} to DB: {e}")


# Singleton instance
conversation_manager = ConversationManager()
