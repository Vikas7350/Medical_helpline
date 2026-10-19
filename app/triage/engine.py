"""Medical Safety and Triage Engine.

Enforces strict triage boundaries:
1. Immediate emergency detection bypass.
2. Escalation for high severity or prolonged duration.
3. Ambiguity handling (never declares safe).
4. Guardrail enforcement against prescription, diagnosis, or unsupported claims.
"""

import re
from dataclasses import dataclass
from typing import Optional
from app.triage.rules import (
    ALL_TRIAGE_RULES,
    EMERGENCY_RULES,
    GENERAL_GUIDANCE_RULES,
    PROMPT_ASSESSMENT_RULES,
    TriageRule,
    UrgencyLevel,
)

# Standard non-diagnostic disclaimer in supported languages
NON_DIAGNOSTIC_DISCLAIMER = {
    "en": "Note: This automated helpline provides initial first-aid information and is not a substitute for a qualified doctor.",
    "hi": "महत्वपूर्ण सूचना: यह स्वचालित हेल्पलाइन प्राथमिक जानकारी देती है और किसी योग्य डॉक्टर का विकल्प नहीं है।",
    "mr": "महत्त्वाची सूचना: ही स्वयंचलित हेल्पलाइन केवळ प्राथमिक माहितीसाठी आहे, हा कोणत्याही पात्र डॉक्टरांचा पर्याय नाही.",
}

# Forbidden keywords indicating prescription or inappropriate safety declaration
PROHIBITED_PRESCRIPTION_PATTERNS = [
    re.compile(r"\b(take|consume|prescribe)\b.*\b\d+\s*(mg|ml|tablets?|capsules?)\b", re.IGNORECASE),
    re.compile(r"\b(paracetamol|amoxicillin|ibuprofen|antibiotics?|aspirin|azithromycin)\b", re.IGNORECASE),
    re.compile(r"\b(पैरासिटामोल|एंटीबायोटिक|दवा ले लें|गोली खा लें)\b", re.IGNORECASE),
    re.compile(r"\b(पॅरासिटामॉल|गोळी घ्या|औषध घ्या)\b", re.IGNORECASE),
]

PROHIBITED_SAFE_PATTERNS = [
    re.compile(r"\b(you are (completely )?safe|nothing to worry about|no illness|guaranteed cure)\b", re.IGNORECASE),
    re.compile(r"\b(आप बिल्कुल ठीक हैं|चिंता की कोई बात नहीं|कोई बीमारी नहीं है)\b", re.IGNORECASE),
    re.compile(r"\b(तुम्हाला काहीही काळजी नाही|तुम्ही पूर्णपणे सुरक्षित आहात)\b", re.IGNORECASE),
]

PROHIBITED_DIAGNOSIS_PATTERNS = [
    re.compile(r"\b(you are diagnosed with|you definitely have|you suffer from)\b", re.IGNORECASE),
    re.compile(r"\b(आपको निश्चित रूप से .* रोग है|बीमारी का निदान)\b", re.IGNORECASE),
    re.compile(r"\b(तुम्हाला निश्चितपणे .* आजार आहे)\b", re.IGNORECASE),
]


@dataclass
class TriageAssessment:
    symptom_category: str
    urgency_category: UrgencyLevel
    is_emergency: bool
    referral_recommended: bool
    matched_rule_id: Optional[str]
    clinical_rationale: str
    guidance_text: str
    disclaimer: str


class TriageEngine:
    """Triage evaluator applying clinician-reviewable rules and safety filters."""

    @classmethod
    def evaluate(
        cls,
        symptom_text: str,
        language: str = "en",
        duration_days: Optional[int] = None,
        severity_score: Optional[int] = None,
    ) -> TriageAssessment:
        normalized_text = (symptom_text or "").lower().strip()
        lang = language if language in ("en", "hi", "mr") else "en"
        disclaimer = NON_DIAGNOSTIC_DISCLAIMER[lang]

        # STEP 1: Emergency Red Flag Screening (Immediate Bypass)
        for rule in EMERGENCY_RULES:
            if cls._matches_rule(normalized_text, rule):
                guidance = getattr(rule, f"guidance_summary_{lang}")
                return TriageAssessment(
                    symptom_category=rule.symptom_category,
                    urgency_category="emergency",
                    is_emergency=True,
                    referral_recommended=True,
                    matched_rule_id=rule.rule_id,
                    clinical_rationale=rule.clinical_rationale,
                    guidance_text=guidance,
                    disclaimer=disclaimer,
                )

        # STEP 2: Check for prompt medical assessment rules
        for rule in PROMPT_ASSESSMENT_RULES:
            if cls._matches_rule(normalized_text, rule):
                guidance = getattr(rule, f"guidance_summary_{lang}")
                return TriageAssessment(
                    symptom_category=rule.symptom_category,
                    urgency_category="prompt_assessment",
                    is_emergency=False,
                    referral_recommended=True,
                    matched_rule_id=rule.rule_id,
                    clinical_rationale=rule.clinical_rationale,
                    guidance_text=guidance,
                    disclaimer=disclaimer,
                )

        # STEP 3: Escalation based on duration (> 3 days) or severity (>= 7/10)
        if (duration_days is not None and duration_days >= 3) or (severity_score is not None and severity_score >= 7):
            escalation_msg = {
                "en": (
                    "Prompt Assessment: Your symptoms have lasted over 3 days or have high severity. "
                    "We recommend a physical checkup at your nearest Primary Health Centre or Community Health Centre."
                ),
                "hi": (
                    "शीघ्र चिकित्सकीय परामर्श: आपके लक्षण 3 दिन से अधिक समय से हैं या अधिक गंभीर हैं। "
                    "कृपया नजदीकी प्राथमिक स्वास्थ्य केंद्र या डॉक्टर से जांच करवाएं।"
                ),
                "mr": (
                    "त्वरित वैद्यकीय सल्ला: तुमची लक्षणे ३ दिवसांपेक्षा जास्त काळापासून आहेत किंवा तीव्र आहेत. "
                    "कृपया जवळच्या प्राथमिक आरोग्य केंद्रात डॉक्टरांकडून तपासणी करून घ्या."
                ),
            }[lang]

            return TriageAssessment(
                symptom_category="prolonged_symptoms",
                urgency_category="prompt_assessment",
                is_emergency=False,
                referral_recommended=True,
                matched_rule_id="ESCALATE_DURATION_SEVERITY",
                clinical_rationale="Escalation due to duration >= 3 days or severity score >= 7/10.",
                guidance_text=escalation_msg,
                disclaimer=disclaimer,
            )

        # STEP 4: Check for general mild guidance
        for rule in GENERAL_GUIDANCE_RULES:
            if cls._matches_rule(normalized_text, rule):
                guidance = getattr(rule, f"guidance_summary_{lang}")
                return TriageAssessment(
                    symptom_category=rule.symptom_category,
                    urgency_category="general_guidance",
                    is_emergency=False,
                    referral_recommended=False,
                    matched_rule_id=rule.rule_id,
                    clinical_rationale=rule.clinical_rationale,
                    guidance_text=guidance,
                    disclaimer=disclaimer,
                )

        # STEP 5: Ambiguous / Unclear symptoms fallback
        # Rule: AI must NOT declare safe. When uncertain, recommend professional evaluation.
        ambiguity_msg = {
            "en": (
                "General Advice: We could not determine a specific match for your symptoms. "
                "Because phone triage has limitations, please consult your local village health worker (ASHA/ANM) "
                "or visit the Primary Health Centre if you feel unwell or if your condition changes."
            ),
            "hi": (
                "सामान्य सलाह: आपके लक्षणों का स्पष्ट अनुमान नहीं लगाया जा सका। "
                "यदि आप अस्वस्थ महसूस कर रहे हैं, तो कृपया अपनी आशा दीदी से संपर्क करें या प्राथमिक स्वास्थ्य केंद्र जाकर डॉक्टर को दिखाएं।"
            ),
            "mr": (
                "सामान्य सल्ला: तुमच्या लक्षणांचा स्पष्ट अंदाज लावता आला नाही. "
                "जर तुम्हाला बरे वाटत नसेल, तर कृपया तुमच्या आशा ताईंशी संपर्क साधा किंवा प्राथमिक आरोग्य केंद्राला भेट द्या."
            ),
        }[lang]

        return TriageAssessment(
            symptom_category="unspecified",
            urgency_category="prompt_assessment",  # Safe default when unclear
            is_emergency=False,
            referral_recommended=True,
            matched_rule_id="FALLBACK_UNCERTAIN",
            clinical_rationale="Unclear/ambiguous symptoms default to professional consultation recommendation.",
            guidance_text=ambiguity_msg,
            disclaimer=disclaimer,
        )

    @classmethod
    def _matches_rule(cls, text: str, rule: TriageRule) -> bool:
        """Check if any keyword phrase or co-occurring key clinical terms match."""
        all_keywords = rule.keywords_en + rule.keywords_hi + rule.keywords_mr
        for kw in all_keywords:
            kw_clean = kw.lower().strip()
            if kw_clean in text:
                return True
            # Also check co-occurring key terms (e.g. 'chest' & 'pain', 'सीने' & 'दर्द', 'छातीत' & 'वेदना')
            parts = [
                p for p in kw_clean.split()
                if len(p) >= 3 and p not in ("and", "with", "the", "for", "में", "आहे", "होत", "होने", "आणि")
            ]
            if len(parts) >= 2 and all(part in text for part in parts):
                return True
        return False

    @classmethod
    def validate_safety_guardrails(cls, text: str, fallback_lang: str = "en") -> str:
        """Check and sanitize any generated output against prescription, definitive diagnosis, or false safety."""
        cleaned_text = text

        for pattern in PROHIBITED_PRESCRIPTION_PATTERNS:
            if pattern.search(cleaned_text):
                return {
                    "en": "Please consult a registered doctor or Primary Health Centre for any medication prescriptions.",
                    "hi": "दवाओं के पर्चे या गोली लेने के लिए कृपया योग्य डॉक्टर या प्राथमिक स्वास्थ्य केंद्र से संपर्क करें।",
                    "mr": "कोणतीही औषधे किंवा गोळ्या घेण्यासाठी कृपया डॉक्टरांचा किंवा प्राथमिक आरोग्य केंद्राचा सल्ला घ्या.",
                }.get(fallback_lang, "Please consult a doctor for prescription medication.")

        for pattern in PROHIBITED_SAFE_PATTERNS:
            if pattern.search(cleaned_text):
                cleaned_text = pattern.sub("", cleaned_text).strip()

        for pattern in PROHIBITED_DIAGNOSIS_PATTERNS:
            if pattern.search(cleaned_text):
                cleaned_text = pattern.sub("your reported symptoms may relate to", cleaned_text).strip()

        return cleaned_text
