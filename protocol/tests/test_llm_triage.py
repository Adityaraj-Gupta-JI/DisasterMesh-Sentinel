"""LLM-based triage: config-gated, and must never block a report.

No real network call is made — httpx.post is monkeypatched so these tests
run offline and deterministically, same as everything else in this suite.
"""

from __future__ import annotations

import httpx
import pytest
from dms.ai import get_triage_model
from dms.ai.base import AIError
from dms.ai.llm import FallbackTriageModel, LlmTriageModel
from dms.domain.enums import DisasterType, Urgency


def _fake_response(json_body: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("POST", "https://example.invalid/chat")
    return httpx.Response(status_code, json=json_body, request=request)


def test_mode_defaults_to_rules_based_triage(monkeypatch):
    monkeypatch.delenv("DMS_AI_MODE", raising=False)
    model = get_triage_model()
    result = model.triage("Three people trapped under collapsed building")
    assert result.model.mode == "mock"  # the rule engine's own ModelInfo


def test_llm_mode_selects_the_fallback_wrapper(monkeypatch):
    monkeypatch.setenv("DMS_AI_MODE", "llm")
    assert isinstance(get_triage_model(), FallbackTriageModel)


def test_llm_without_api_key_raises_a_structured_error(monkeypatch):
    monkeypatch.delenv("DMS_AI_LLM_API_KEY", raising=False)
    with pytest.raises(AIError):
        LlmTriageModel().triage("test")


def test_llm_parses_a_well_formed_response(monkeypatch):
    monkeypatch.setenv("DMS_AI_LLM_API_KEY", "test-key")

    def fake_post(url, *, headers, json, timeout):
        content = (
            '{"urgency": "CRITICAL", "disaster_types": ["BUILDING_COLLAPSE"], '
            '"severity": 90, "confidence": 0.8, "safety_flags": ["immediate_life_threat"]}'
        )
        return _fake_response({"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    result = LlmTriageModel().triage("Three people trapped under collapsed building")
    assert result.urgency is Urgency.CRITICAL
    assert DisasterType.BUILDING_COLLAPSE in result.disaster_types
    assert result.severity == 90
    assert result.model.mode == "real"


def test_llm_malformed_json_raises(monkeypatch):
    monkeypatch.setenv("DMS_AI_LLM_API_KEY", "test-key")

    def fake_post(url, *, headers, json, timeout):
        return _fake_response({"choices": [{"message": {"content": "not json"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(AIError):
        LlmTriageModel().triage("test")


def test_llm_network_failure_raises(monkeypatch):
    monkeypatch.setenv("DMS_AI_LLM_API_KEY", "test-key")

    def fake_post(url, *, headers, json, timeout):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(AIError):
        LlmTriageModel().triage("test")


def test_fallback_model_never_raises_and_uses_rules_on_llm_failure(monkeypatch):
    """The core guarantee: whatever goes wrong with the LLM, a report still
    gets triaged via the deterministic engine, never blocked or crashed."""
    monkeypatch.delenv("DMS_AI_LLM_API_KEY", raising=False)  # guarantees the LLM call fails
    result = FallbackTriageModel().triage("Three people trapped under collapsed building")
    assert result.urgency is Urgency.CRITICAL
    assert result.model.mode == "mock"  # silently landed on the rule engine
