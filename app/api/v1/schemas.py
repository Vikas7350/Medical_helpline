from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    is_synthetic: bool = Field(default=False, description="Whether this is a synthetic demo/test interaction")
    initial_language: Optional[str] = Field(default=None, description="Optional pre-selected language: en, hi, mr")


class CreateSessionResponse(BaseModel):
    session_id: str
    state: str
    spoken_text: str
    options: List[Dict[str, str]]
    created_at: str


class LanguageSelectRequest(BaseModel):
    language: str = Field(..., description="Language choice: '1'/'en', '2'/'hi', or '3'/'mr'")


class TurnRequest(BaseModel):
    user_input: Optional[str] = Field(default=None, description="Spoken text or simulated speech transcript")
    audio_base64: Optional[str] = Field(default=None, description="Optional audio recording base64 string")
    is_dtmf: bool = Field(default=False, description="True if input originates from a telephone keypad button press")


class TriageInfo(BaseModel):
    symptom_category: str
    urgency_category: str
    is_emergency: bool
    referral_recommended: bool
    matched_rule_id: Optional[str] = None
    clinical_rationale: Optional[str] = None


class TurnResponse(BaseModel):
    session_id: str
    state: str
    spoken_text: str
    language: str
    is_completed: bool
    should_hangup: bool
    requires_dtmf: bool
    triage: Optional[TriageInfo] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
    timestamp: str
    telephony_provider: str


class AnalyticsResponse(BaseModel):
    total_interactions: int
    languages: Dict[str, int]
    symptom_categories: Dict[str, int]
    urgency_distribution: Dict[str, int]
    referrals: Dict[str, Any]
    completion: Dict[str, Any]
    synthetic_records_count: int
    live_records_count: int


class ReportItem(BaseModel):
    session_id: str
    selected_language: Optional[str]
    symptom_category: Optional[str]
    urgency_category: str
    referral_recommended: bool
    is_completed: bool
    duration_seconds: int
    turns_count: int
    is_synthetic: bool
    created_at: Optional[str]
    completed_at: Optional[str]


class ReportsListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[ReportItem]
