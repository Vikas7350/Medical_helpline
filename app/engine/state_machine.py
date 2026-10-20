"""Conversation state machine for rural feature phone IVR helpline."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from app.engine.localization import WELCOME_IVR_MENU, get_prompt
from app.engine.parsers import (
    is_exit_command,
    is_repeat_command,
    parse_duration,
    parse_severity,
    parse_yes_no,
)
from app.triage.engine import TriageAssessment, TriageEngine


class ConversationState(str, Enum):
    LANGUAGE_SELECT = "LANGUAGE_SELECT"
    SYMPTOM_INPUT = "SYMPTOM_INPUT"
    DURATION_INPUT = "DURATION_INPUT"
    SEVERITY_INPUT = "SEVERITY_INPUT"
    EMERGENCY_CONFIRMATION = "EMERGENCY_CONFIRMATION"
    GUIDANCE_DELIVERED = "GUIDANCE_DELIVERED"
    COMPLETED = "COMPLETED"
    DISCONNECTED = "DISCONNECTED"


@dataclass
class ConversationContext:
    session_id: str
    state: ConversationState = ConversationState.LANGUAGE_SELECT
    language: Optional[str] = None  # "en", "hi", "mr"
    symptoms_text: str = ""
    duration_days: Optional[int] = None
    severity_level: Optional[int] = None  # 1 (mild) to 10 (severe)
    emergency_confirmed: Optional[bool] = None
    triage_assessment: Optional[TriageAssessment] = None
    unrecognized_count: int = 0
    turns_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_spoken_prompt: str = WELCOME_IVR_MENU
    is_completed: bool = False
    is_synthetic: bool = False


@dataclass
class TurnResult:
    next_state: ConversationState
    spoken_text: str
    language: str
    is_completed: bool
    should_hangup: bool
    requires_dtmf: bool
    triage_assessment: Optional[TriageAssessment] = None


class HelplineStateMachine:
    """State machine governing call flow from IVR language menu to safe triage exit."""

    @classmethod
    def process_turn(
        cls,
        context: ConversationContext,
        caller_input: str,
        is_dtmf: bool = False,
    ) -> TurnResult:
        context.turns_count += 1
        caller_input = (caller_input or "").strip()

        # Global command: DTMF 9 or speech "goodbye/exit" ends the call
        if is_exit_command(caller_input):
            lang = context.language or "en"
            context.state = ConversationState.COMPLETED
            context.is_completed = True
            goodbye_msg = get_prompt("goodbye", lang)
            return TurnResult(
                next_state=ConversationState.COMPLETED,
                spoken_text=goodbye_msg,
                language=lang,
                is_completed=True,
                should_hangup=True,
                requires_dtmf=False,
                triage_assessment=context.triage_assessment,
            )

        # Global command: DTMF 0 repeats the last spoken prompt
        if is_repeat_command(caller_input):
            lang = context.language or "en"
            return TurnResult(
                next_state=context.state,
                spoken_text=f"{context.last_spoken_prompt} {get_prompt('repeat_instruction', lang)}",
                language=lang,
                is_completed=context.is_completed,
                should_hangup=False,
                requires_dtmf=(context.state == ConversationState.LANGUAGE_SELECT),
                triage_assessment=context.triage_assessment,
            )

        # Handle silence / empty input
        if not caller_input:
            context.unrecognized_count += 1
            lang = context.language or "en"
            if context.unrecognized_count >= 3:
                context.state = ConversationState.COMPLETED
                context.is_completed = False
                return TurnResult(
                    next_state=ConversationState.COMPLETED,
                    spoken_text=get_prompt("max_retries", lang),
                    language=lang,
                    is_completed=False,
                    should_hangup=True,
                    requires_dtmf=False,
                )
            silence_prompt = f"{get_prompt('silence', lang)} {context.last_spoken_prompt}"
            return TurnResult(
                next_state=context.state,
                spoken_text=silence_prompt,
                language=lang,
                is_completed=False,
                should_hangup=False,
                requires_dtmf=(context.state == ConversationState.LANGUAGE_SELECT),
            )

        # Route by state
        if context.state == ConversationState.LANGUAGE_SELECT:
            return cls._handle_language_select(context, caller_input)

        elif context.state == ConversationState.SYMPTOM_INPUT:
            return cls._handle_symptom_input(context, caller_input)

        elif context.state == ConversationState.DURATION_INPUT:
            return cls._handle_duration_input(context, caller_input)

        elif context.state == ConversationState.SEVERITY_INPUT:
            return cls._handle_severity_input(context, caller_input)

        elif context.state == ConversationState.EMERGENCY_CONFIRMATION:
            return cls._handle_emergency_confirmation(context, caller_input)

        elif context.state == ConversationState.GUIDANCE_DELIVERED:
            # Caller spoke after guidance was delivered
            lang = context.language or "en"
            goodbye_msg = get_prompt("goodbye", lang)
            context.state = ConversationState.COMPLETED
            context.is_completed = True
            return TurnResult(
                next_state=ConversationState.COMPLETED,
                spoken_text=goodbye_msg,
                language=lang,
                is_completed=True,
                should_hangup=True,
                requires_dtmf=False,
                triage_assessment=context.triage_assessment,
            )

        # Fallback for completed / unknown
        lang = context.language or "en"
        return TurnResult(
            next_state=ConversationState.COMPLETED,
            spoken_text=get_prompt("goodbye", lang),
            language=lang,
            is_completed=True,
            should_hangup=True,
            requires_dtmf=False,
        )

    @classmethod
    def _handle_language_select(cls, context: ConversationContext, user_input: str) -> TurnResult:
        """Process DTMF 1 (English), 2 (Hindi), 3 (Marathi)."""
        input_cleaned = user_input.lower().replace("press", "").strip()

        lang_map = {
            "1": "en", "en": "en", "english": "en",
            "2": "hi", "hi": "hi", "hindi": "hi", "हिंदी": "hi",
            "3": "mr", "mr": "mr", "marathi": "mr", "मराठी": "mr",
        }

        selected_lang = lang_map.get(input_cleaned)

        if not selected_lang:
            context.unrecognized_count += 1
            if context.unrecognized_count >= 3:
                context.state = ConversationState.COMPLETED
                return TurnResult(
                    next_state=ConversationState.COMPLETED,
                    spoken_text="Invalid selection. Please visit your local health clinic. Goodbye.",
                    language="en",
                    is_completed=False,
                    should_hangup=True,
                    requires_dtmf=False,
                )
            # Re-prompt menu
            return TurnResult(
                next_state=ConversationState.LANGUAGE_SELECT,
                spoken_text=f"Please press 1 for English, 2 for Hindi, or 3 for Marathi. {WELCOME_IVR_MENU}",
                language="en",
                is_completed=False,
                should_hangup=False,
                requires_dtmf=True,
            )

        context.language = selected_lang
        context.state = ConversationState.SYMPTOM_INPUT
        context.unrecognized_count = 0
        prompt = get_prompt("welcome", selected_lang)
        context.last_spoken_prompt = prompt

        return TurnResult(
            next_state=ConversationState.SYMPTOM_INPUT,
            spoken_text=prompt,
            language=selected_lang,
            is_completed=False,
            should_hangup=False,
            requires_dtmf=False,
        )

    @classmethod
    def _handle_symptom_input(cls, context: ConversationContext, user_input: str) -> TurnResult:
        """Process spoken description of symptoms and screen for immediate emergency."""
        lang = context.language or "en"
        context.symptoms_text = user_input
        context.unrecognized_count = 0

        # Run clinical triage rule evaluation immediately
        assessment = TriageEngine.evaluate(symptom_text=user_input, language=lang)
        context.triage_assessment = assessment

        # CRITICAL SAFETY RULE: If potential emergency detected, BYPASS follow-up questions immediately!
        if assessment.is_emergency:
            context.state = ConversationState.GUIDANCE_DELIVERED
            context.is_completed = True
            spoken = f"{assessment.guidance_text} {assessment.disclaimer} {get_prompt('repeat_instruction', lang)}"
            context.last_spoken_prompt = spoken
            return TurnResult(
                next_state=ConversationState.GUIDANCE_DELIVERED,
                spoken_text=spoken,
                language=lang,
                is_completed=True,
                should_hangup=False,
                requires_dtmf=False,
                triage_assessment=assessment,
            )

        # Non-emergency: Proceed to ask duration of symptoms
        context.state = ConversationState.DURATION_INPUT
        duration_prompt = get_prompt("ask_duration", lang)
        context.last_spoken_prompt = duration_prompt

        return TurnResult(
            next_state=ConversationState.DURATION_INPUT,
            spoken_text=duration_prompt,
            language=lang,
            is_completed=False,
            should_hangup=False,
            requires_dtmf=False,
            triage_assessment=assessment,
        )

    @classmethod
    def _handle_duration_input(cls, context: ConversationContext, user_input: str) -> TurnResult:
        """Parse symptom duration and proceed to severity question."""
        lang = context.language or "en"

        duration_days = parse_duration(user_input, language=lang)
        if duration_days is None:
            context.unrecognized_count += 1
            if context.unrecognized_count >= 3:
                context.state = ConversationState.COMPLETED
                context.is_completed = False
                return TurnResult(
                    next_state=ConversationState.COMPLETED,
                    spoken_text=get_prompt("max_retries", lang),
                    language=lang,
                    is_completed=False,
                    should_hangup=True,
                    requires_dtmf=False,
                    triage_assessment=context.triage_assessment,
                )
            clarification_text = f"{get_prompt('unrecognized', lang)} {context.last_spoken_prompt}"
            return TurnResult(
                next_state=ConversationState.DURATION_INPUT,
                spoken_text=clarification_text,
                language=lang,
                is_completed=False,
                should_hangup=False,
                requires_dtmf=False,
                triage_assessment=context.triage_assessment,
            )

        # Valid duration recognized
        context.unrecognized_count = 0
        context.duration_days = duration_days

        context.state = ConversationState.SEVERITY_INPUT
        severity_prompt = get_prompt("ask_severity", lang)
        context.last_spoken_prompt = severity_prompt

        return TurnResult(
            next_state=ConversationState.SEVERITY_INPUT,
            spoken_text=severity_prompt,
            language=lang,
            is_completed=False,
            should_hangup=False,
            requires_dtmf=False,
            triage_assessment=context.triage_assessment,
        )

    @classmethod
    def _handle_severity_input(cls, context: ConversationContext, user_input: str) -> TurnResult:
        """Parse severity and deliver triage guidance."""
        lang = context.language or "en"

        severity = parse_severity(user_input, language=lang)
        if severity is None:
            context.unrecognized_count += 1
            if context.unrecognized_count >= 3:
                context.state = ConversationState.COMPLETED
                context.is_completed = False
                return TurnResult(
                    next_state=ConversationState.COMPLETED,
                    spoken_text=get_prompt("max_retries", lang),
                    language=lang,
                    is_completed=False,
                    should_hangup=True,
                    requires_dtmf=False,
                    triage_assessment=context.triage_assessment,
                )
            clarification_text = f"{get_prompt('unrecognized', lang)} {context.last_spoken_prompt}"
            return TurnResult(
                next_state=ConversationState.SEVERITY_INPUT,
                spoken_text=clarification_text,
                language=lang,
                is_completed=False,
                should_hangup=False,
                requires_dtmf=False,
                triage_assessment=context.triage_assessment,
            )

        # Valid severity recognized
        context.unrecognized_count = 0
        context.severity_level = severity

        # Re-evaluate triage with duration and severity incorporated
        assessment = TriageEngine.evaluate(
            symptom_text=context.symptoms_text,
            language=lang,
            duration_days=context.duration_days,
            severity_score=context.severity_level,
        )
        context.triage_assessment = assessment

        # Deliver comprehensive guidance
        context.state = ConversationState.GUIDANCE_DELIVERED
        context.is_completed = True
        spoken = f"{assessment.guidance_text} {assessment.disclaimer} {get_prompt('repeat_instruction', lang)}"
        context.last_spoken_prompt = spoken

        return TurnResult(
            next_state=ConversationState.GUIDANCE_DELIVERED,
            spoken_text=spoken,
            language=lang,
            is_completed=True,
            should_hangup=False,
            requires_dtmf=False,
            triage_assessment=assessment,
        )

    @classmethod
    def _handle_emergency_confirmation(cls, context: ConversationContext, user_input: str) -> TurnResult:
        """Handle explicit check for emergency red flags."""
        lang = context.language or "en"

        is_yes = parse_yes_no(user_input, language=lang)
        if is_yes is None:
            context.unrecognized_count += 1
            if context.unrecognized_count >= 3:
                context.state = ConversationState.COMPLETED
                context.is_completed = False
                return TurnResult(
                    next_state=ConversationState.COMPLETED,
                    spoken_text=get_prompt("max_retries", lang),
                    language=lang,
                    is_completed=False,
                    should_hangup=True,
                    requires_dtmf=False,
                    triage_assessment=context.triage_assessment,
                )
            clarification_text = f"{get_prompt('unrecognized', lang)} {context.last_spoken_prompt}"
            return TurnResult(
                next_state=ConversationState.EMERGENCY_CONFIRMATION,
                spoken_text=clarification_text,
                language=lang,
                is_completed=False,
                should_hangup=False,
                requires_dtmf=False,
                triage_assessment=context.triage_assessment,
            )

        context.unrecognized_count = 0
        context.emergency_confirmed = is_yes

        if is_yes:
            # Caller confirmed emergency signs
            assessment = TriageEngine.evaluate("chest pain severe breathing problem", language=lang)
            context.triage_assessment = assessment
        else:
            assessment = TriageEngine.evaluate(
                symptom_text=context.symptoms_text,
                language=lang,
                duration_days=context.duration_days,
                severity_score=context.severity_level,
            )
            context.triage_assessment = assessment

        context.state = ConversationState.GUIDANCE_DELIVERED
        context.is_completed = True
        spoken = f"{assessment.guidance_text} {assessment.disclaimer} {get_prompt('repeat_instruction', lang)}"
        context.last_spoken_prompt = spoken

        return TurnResult(
            next_state=ConversationState.GUIDANCE_DELIVERED,
            spoken_text=spoken,
            language=lang,
            is_completed=True,
            should_hangup=False,
            requires_dtmf=False,
            triage_assessment=assessment,
        )
