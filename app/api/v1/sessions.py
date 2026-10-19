import uuid
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import DatabaseSession
from app.api.v1.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    LanguageSelectRequest,
    TriageInfo,
    TurnRequest,
    TurnResponse,
)
from app.engine.conversation import conversation_manager
from app.engine.localization import WELCOME_IVR_MENU
from app.services.stt import get_stt_service

router = APIRouter(prefix="/sessions", tags=["Helpline Sessions"])


@router.post("", response_model=CreateSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: Optional[CreateSessionRequest] = None,
    db: Session = DatabaseSession,
):
    """Create a temporary rural medical helpline session."""
    req = payload or CreateSessionRequest()
    session_id = str(uuid.uuid4())

    ctx, spoken_text = conversation_manager.get_or_create_context(
        session_id=session_id,
        is_synthetic=req.is_synthetic,
        db=db,
    )

    # If caller pre-selected language (e.g. from app or IVR shortcut)
    if req.initial_language:
        await conversation_manager.select_language(session_id, req.initial_language, db=db)
        spoken_text = ctx.last_spoken_prompt

    options = [
        {"digit": "1", "label": "English"},
        {"digit": "2", "label": "Hindi (हिंदी)"},
        {"digit": "3", "label": "Marathi (मराठी)"},
        {"digit": "0", "label": "Repeat menu"},
        {"digit": "9", "label": "End call"},
    ]

    return CreateSessionResponse(
        session_id=ctx.session_id,
        state=ctx.state.value,
        spoken_text=spoken_text,
        options=options,
        created_at=ctx.created_at.isoformat(),
    )


@router.get("/{session_id}", response_model=TurnResponse)
async def get_session_status(session_id: str):
    """Retrieve current conversation state and prompt."""
    ctx = conversation_manager.get_context(session_id)
    if not ctx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Helpline session '{session_id}' not found or has expired.",
        )

    triage_info = None
    if ctx.triage_assessment:
        triage_info = TriageInfo(
            symptom_category=ctx.triage_assessment.symptom_category,
            urgency_category=ctx.triage_assessment.urgency_category,
            is_emergency=ctx.triage_assessment.is_emergency,
            referral_recommended=ctx.triage_assessment.referral_recommended,
            matched_rule_id=ctx.triage_assessment.matched_rule_id,
            clinical_rationale=ctx.triage_assessment.clinical_rationale,
        )

    return TurnResponse(
        session_id=ctx.session_id,
        state=ctx.state.value,
        spoken_text=ctx.last_spoken_prompt,
        language=ctx.language or "en",
        is_completed=ctx.is_completed,
        should_hangup=(ctx.state.value in ("COMPLETED", "DISCONNECTED")),
        requires_dtmf=(ctx.state.value == "LANGUAGE_SELECT"),
        triage=triage_info,
    )


@router.post("/{session_id}/language", response_model=TurnResponse)
async def select_session_language(
    session_id: str,
    payload: LanguageSelectRequest,
    db: Session = DatabaseSession,
):
    """Select conversation language via digit ('1', '2', '3') or language code ('en', 'hi', 'mr')."""
    turn_res = await conversation_manager.select_language(
        session_id=session_id,
        language_or_digit=payload.language,
        db=db,
    )

    triage_info = None
    if turn_res.triage_assessment:
        triage_info = TriageInfo(
            symptom_category=turn_res.triage_assessment.symptom_category,
            urgency_category=turn_res.triage_assessment.urgency_category,
            is_emergency=turn_res.triage_assessment.is_emergency,
            referral_recommended=turn_res.triage_assessment.referral_recommended,
            matched_rule_id=turn_res.triage_assessment.matched_rule_id,
            clinical_rationale=turn_res.triage_assessment.clinical_rationale,
        )

    return TurnResponse(
        session_id=session_id,
        state=turn_res.next_state.value,
        spoken_text=turn_res.spoken_text,
        language=turn_res.language,
        is_completed=turn_res.is_completed,
        should_hangup=turn_res.should_hangup,
        requires_dtmf=turn_res.requires_dtmf,
        triage=triage_info,
    )


@router.post("/{session_id}/turn", response_model=TurnResponse)
async def process_turn(
    session_id: str,
    payload: TurnRequest,
    db: Session = DatabaseSession,
):
    """Process a turn of simulated caller speech or button-phone DTMF input."""
    caller_text = payload.user_input

    # If audio_base64 provided, transcribe with STT service
    if payload.audio_base64:
        stt = get_stt_service()
        ctx = conversation_manager.get_context(session_id)
        lang = ctx.language if ctx and ctx.language else "en"
        caller_text = await stt.transcribe(payload.audio_base64.encode("utf-8"), language=lang)

    turn_res = await conversation_manager.process_turn(
        session_id=session_id,
        caller_input=caller_text or "",
        is_dtmf=payload.is_dtmf,
        db=db,
    )

    triage_info = None
    if turn_res.triage_assessment:
        triage_info = TriageInfo(
            symptom_category=turn_res.triage_assessment.symptom_category,
            urgency_category=turn_res.triage_assessment.urgency_category,
            is_emergency=turn_res.triage_assessment.is_emergency,
            referral_recommended=turn_res.triage_assessment.referral_recommended,
            matched_rule_id=turn_res.triage_assessment.matched_rule_id,
            clinical_rationale=turn_res.triage_assessment.clinical_rationale,
        )

    return TurnResponse(
        session_id=session_id,
        state=turn_res.next_state.value,
        spoken_text=turn_res.spoken_text,
        language=turn_res.language,
        is_completed=turn_res.is_completed,
        should_hangup=turn_res.should_hangup,
        requires_dtmf=turn_res.requires_dtmf,
        triage=triage_info,
    )
