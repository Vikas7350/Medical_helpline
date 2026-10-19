from typing import Any, Dict, Optional
from app.core.config import settings
from app.core.logging import logger
from app.services.base import BaseLLMService
from app.triage.engine import TriageEngine


class MockLLMService(BaseLLMService):
    """Deterministic, clinician-aligned offline LLM service with zero external dependencies."""

    async def generate_guidance(
        self,
        symptom_text: str,
        language: str = "en",
        triage_guidance: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        lang = language if language in ("en", "hi", "mr") else "en"

        logger.info(
            f"[MOCK_LLM] Generating offline clinician-aligned triage response for language='{lang}'. "
            f"Note: Real external LLM provider is disabled."
        )

        if triage_guidance:
            raw_text = triage_guidance
        else:
            assessment = TriageEngine.evaluate(symptom_text, language=lang)
            raw_text = f"{assessment.guidance_text} {assessment.disclaimer}"

        # Enforce safety guardrails against any unintended claims
        return TriageEngine.validate_safety_guardrails(raw_text, fallback_lang=lang)


class OpenAILLMService(BaseLLMService):
    """OpenAI-backed guidance generator with strict medical safety system prompt."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def generate_guidance(
        self,
        symptom_text: str,
        language: str = "en",
        triage_guidance: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        lang = language if language in ("en", "hi", "mr") else "en"
        try:
            import httpx

            lang_instructions = {
                "en": "Respond in natural, fluent English.",
                "hi": (
                    "You MUST respond exclusively in natural, fluent Hindi written in standard Devanagari script (देवनागरी लिपि). "
                    "Do NOT use Latin/Roman English alphabet or Hinglish."
                ),
                "mr": (
                    "You MUST respond exclusively in natural, fluent Marathi written in standard Devanagari script (देवनागरी लिपी). "
                    "Do NOT use Latin/Roman English alphabet or Marathlish."
                ),
            }
            system_prompt = (
                f"You are an empathetic, calm medical helpline assistant for rural India. {lang_instructions.get(lang, 'Respond in English.')}\n"
                "CRITICAL MEDICAL RULES:\n"
                "1. NEVER diagnose a condition.\n"
                "2. NEVER prescribe medication, drug names, or dosages.\n"
                "3. NEVER declare a caller 100% safe.\n"
                "4. Incorporate this clinical triage guidance accurately: "
                f"{triage_guidance or 'Refer to Primary Health Centre.'}\n"
                "5. Keep the response concise, clear, and easy to understand over a basic button phone call."
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"The caller described: '{symptom_text}'"},
                        ],
                        "max_tokens": 200,
                        "temperature": 0.2,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if lang in ("hi", "mr"):
                        has_devanagari = any("\u0900" <= ch <= "\u097f" for ch in content)
                        if not has_devanagari:
                            logger.warning(
                                f"OpenAI LLM response for language '{lang}' did not contain Devanagari script. "
                                "Falling back to verified clinical offline guidance."
                            )
                            return await MockLLMService().generate_guidance(
                                symptom_text, language=lang, triage_guidance=triage_guidance, context=context
                            )
                    return TriageEngine.validate_safety_guardrails(content, fallback_lang=lang)
        except Exception as e:
            logger.warning(f"OpenAI LLM error ({e}), falling back to offline mock service")

        # Fallback to deterministic offline guidance
        return await MockLLMService().generate_guidance(symptom_text, language=lang, triage_guidance=triage_guidance, context=context)


class GrokLLMService(BaseLLMService):
    """xAI Grok-backed clinical guidance generator with strict medical safety system prompt."""

    def __init__(self, api_key: str, model: str = "grok-2-latest"):
        self.api_key = api_key
        self.model = model

    async def generate_guidance(
        self,
        symptom_text: str,
        language: str = "en",
        triage_guidance: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        lang = language if language in ("en", "hi", "mr") else "en"
        try:
            import httpx

            lang_instructions = {
                "en": "Respond in natural, fluent English.",
                "hi": (
                    "You MUST respond exclusively in natural, fluent Hindi written in standard Devanagari script (देवनागरी लिपि). "
                    "Do NOT use Latin/Roman English alphabet or Hinglish."
                ),
                "mr": (
                    "You MUST respond exclusively in natural, fluent Marathi written in standard Devanagari script (देवनागरी लिपी). "
                    "Do NOT use Latin/Roman English alphabet or Marathlish."
                ),
            }
            system_prompt = (
                f"You are an empathetic, calm medical helpline assistant for rural India. {lang_instructions.get(lang, 'Respond in English.')}\n"
                "CRITICAL MEDICAL RULES:\n"
                "1. NEVER diagnose a condition.\n"
                "2. NEVER prescribe medication, drug names, or dosages.\n"
                "3. NEVER declare a caller 100% safe.\n"
                "4. Incorporate this clinical triage guidance accurately: "
                f"{triage_guidance or 'Refer to Primary Health Centre.'}\n"
                "5. Keep the response concise, clear, and easy to understand over a basic button phone call."
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": f"The caller described: '{symptom_text}'"},
                        ],
                        "max_tokens": 200,
                        "temperature": 0.2,
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if lang in ("hi", "mr"):
                        has_devanagari = any("\u0900" <= ch <= "\u097f" for ch in content)
                        if not has_devanagari:
                            logger.warning(
                                f"xAI Grok response for language '{lang}' did not contain Devanagari script. "
                                "Falling back to verified clinical offline guidance."
                            )
                            return await MockLLMService().generate_guidance(
                                symptom_text, language=lang, triage_guidance=triage_guidance, context=context
                            )
                    return TriageEngine.validate_safety_guardrails(content, fallback_lang=lang)
                else:
                    logger.warning(
                        f"xAI Grok API returned HTTP {response.status_code}: {response.text[:200]}"
                    )
        except Exception as e:
            safe_err = f"{type(e).__name__}: {e}"
            if self.api_key and self.api_key in safe_err:
                safe_err = safe_err.replace(self.api_key, "[REDACTED]")
            logger.warning(f"xAI Grok LLM error ({safe_err}), falling back to offline mock service")

        # Fallback to deterministic offline clinical rule engine
        return await MockLLMService().generate_guidance(
            symptom_text, language=lang, triage_guidance=triage_guidance, context=context
        )


def get_llm_service() -> BaseLLMService:
    """Factory returning configured LLM provider."""
    provider = settings.LLM_PROVIDER.lower()
    if provider in ("grok", "xai") and getattr(settings, "XAI_API_KEY", None):
        return GrokLLMService(api_key=settings.XAI_API_KEY)
    if provider == "openai" and getattr(settings, "OPENAI_API_KEY", None):
        return OpenAILLMService(api_key=settings.OPENAI_API_KEY)
    return MockLLMService()
