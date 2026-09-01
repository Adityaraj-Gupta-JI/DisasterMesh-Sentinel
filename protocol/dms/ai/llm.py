"""Optional cloud-LLM triage adapter — off by default.

This calls a third-party API with incident text, which can include medical or
location detail. That is a real privacy/offline tradeoff against this
project's offline-first default, so it is inert unless a deployer explicitly
sets ``DMS_AI_MODE=llm`` and supplies their own API key — never on by default,
and never decided on behalf of a deployment that hasn't opted in.

Provider-agnostic: any OpenAI-compatible chat-completions endpoint (Groq,
OpenRouter, etc.) works by pointing ``DMS_AI_LLM_PROVIDER_URL``/
``DMS_AI_LLM_MODEL`` at it — no provider SDK is added as a dependency, just
plain ``httpx`` (already a project dependency).

Falls back to the deterministic rule engine (``dms.ai.rules.triage``) on any
failure — network error, timeout, invalid key, malformed JSON. This is not
optional behavior: a cloud API being unreachable is a routine, expected
condition for an app whose core promise is working without internet, and a
triage call must never block or crash a report.
"""

from __future__ import annotations

import json
import os

import httpx

from ..domain.enums import DisasterType, Urgency
from . import rules
from .base import AIError, ModelInfo, TriageResult, input_hash

MODEL_NAME = "dms-llm-triage"
DEFAULT_PROVIDER_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"

_PROMPT = """You triage a single emergency report for a disaster-response system.
Return ONLY a JSON object with exactly these fields, no prose, no markdown:
{{
  "urgency": one of {urgencies},
  "disaster_types": a list using only values from {disaster_types},
  "severity": integer 0-100,
  "confidence": float 0-1,
  "safety_flags": short list of strings (e.g. "immediate_life_threat"), may be empty
}}

Report text: {text}"""


def _config() -> tuple[str, str, str, float]:
    url = os.getenv("DMS_AI_LLM_PROVIDER_URL", DEFAULT_PROVIDER_URL)
    key = os.getenv("DMS_AI_LLM_API_KEY", "")
    model = os.getenv("DMS_AI_LLM_MODEL", DEFAULT_MODEL)
    timeout = float(os.getenv("DMS_AI_TIMEOUT_S", "10"))
    return url, key, model, timeout


class LlmTriageModel:
    """Conforms to the `TriageModel` protocol: `.triage(text, language=None)`."""

    def triage(self, text: str, language: str | None = None) -> TriageResult:
        url, key, model, timeout = _config()
        if not key:
            raise AIError("llm_not_configured", "DMS_AI_LLM_API_KEY is not set")

        prompt = _PROMPT.format(
            urgencies=[u.value for u in Urgency],
            disaster_types=[d.value for d in DisasterType],
            text=text,
        )
        try:
            response = httpx.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
                timeout=timeout,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except Exception as exc:
            # Network error, timeout, non-2xx, or non-JSON body — all the same
            # to a caller: the LLM path failed, fall back to rules.
            raise AIError("llm_call_failed", str(exc)) from exc

        try:
            urgency = Urgency(parsed["urgency"])
            disaster_types = tuple(
                DisasterType(d)
                for d in parsed.get("disaster_types", [])
                if d in DisasterType.__members__
            ) or (DisasterType.OTHER,)
            severity = max(0, min(100, int(parsed["severity"])))
            confidence = max(0.0, min(1.0, float(parsed["confidence"])))
            safety_flags = tuple(str(f) for f in parsed.get("safety_flags", []))
        except (KeyError, ValueError, TypeError) as exc:
            raise AIError("llm_bad_response", f"malformed triage JSON: {exc}") from exc

        return TriageResult(
            urgency=urgency,
            disaster_types=disaster_types,
            severity=severity,
            confidence=confidence,
            safety_flags=safety_flags,
            explanation_features=(f"llm_model:{model}",),
            model=ModelInfo(name=MODEL_NAME, version=model, mode="real"),
            input_hash=input_hash(text),
        )


class FallbackTriageModel:
    """What `get_triage_model()` returns when `DMS_AI_MODE=llm`: try the LLM,
    and on ANY failure fall back to the deterministic rule engine. Never
    raises — a triage call must never block or crash a report."""

    def __init__(self) -> None:
        self._llm = LlmTriageModel()

    def triage(self, text: str, language: str | None = None) -> TriageResult:
        try:
            return self._llm.triage(text, language)
        except Exception:
            return rules.triage(text, language)
