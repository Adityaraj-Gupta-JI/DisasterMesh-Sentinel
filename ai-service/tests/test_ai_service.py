"""AI service contract tests."""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_health_is_liveness_only(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["mode"]


def test_ready_distinguishes_service_up_from_models_loaded(client):
    body = client.get("/ready").json()
    assert body["status"] in ("ready", "degraded")
    assert isinstance(body["models_loaded"], bool)
    assert body["detail"]


def test_model_registry_is_versioned_and_honest(client):
    models = client.get("/v1/models").json()["models"]
    assert {m["task"] for m in models} >= {
        "transcribe",
        "triage",
        "entities",
        "embed",
        "translate",
        "summarize",
    }
    for model in models:
        assert model["version"] and model["mode"] in ("mock", "real")


def test_triage_returns_model_version_and_input_hash(client):
    body = client.post(
        "/v1/triage", json={"text": "Three people trapped under collapsed building"}
    ).json()
    assert body["urgency"] == "CRITICAL"
    assert "immediate_life_threat" in body["safety_flags"]
    assert body["model"]["version"] and len(body["input_hash"]) == 64
    assert body["advisory"] == "recommendation_only_not_a_dispatch"


@pytest.mark.parametrize(
    "text", ["तीन लोग फंसे हैं", "மூன்று பேர் சிக்கியுள்ளனர்", "building collapse हुआ, trapped"]
)
def test_triage_handles_multilingual_and_code_switched_input(client, text):
    body = client.post("/v1/triage", json={"text": text}).json()
    assert body["urgency"] == "CRITICAL"


def test_blank_text_is_rejected(client):
    assert client.post("/v1/triage", json={"text": "   "}).status_code == 422


def test_oversized_text_is_rejected(client):
    assert client.post("/v1/triage", json={"text": "x" * 9000}).status_code == 422


def test_entities_preserve_raw_spans_and_uncertainty(client):
    body = client.post("/v1/entities", json={"text": "Some people are trapped"}).json()
    assert body["peopleAffected"]["value"] is None
    assert body["peopleAffected"]["approximate"] is True
    assert body["peopleAffected"]["raw"]


def test_transcription_round_trip(client):
    audio = base64.b64encode(b"HI" + b"\x00" * 200).decode()
    body = client.post(
        "/v1/transcribe", json={"audio_base64": audio, "mime_type": "audio/wav"}
    ).json()
    assert body["language"] == "hi" and body["machine_generated"] is True
    assert len(body["audio_sha256"]) == 64


def test_invalid_base64_audio_is_a_structured_error(client):
    response = client.post(
        "/v1/transcribe", json={"audio_base64": "!!!not-base64!!!", "mime_type": "audio/wav"}
    )
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_base64"


def test_unsupported_audio_type_is_a_structured_error(client):
    audio = base64.b64encode(b"EN" + b"\x00" * 50).decode()
    response = client.post(
        "/v1/transcribe", json={"audio_base64": audio, "mime_type": "application/x-sh"}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_media_type"


def test_embeddings_are_normalized_and_batched(client):
    body = client.post("/v1/embed", json={"texts": ["fire", "flood"]}).json()
    assert len(body["embeddings"]) == 2 and body["dimension"] > 0
    vector = body["embeddings"][0]["vector"]
    assert abs(sum(x * x for x in vector) - 1.0) < 1e-9


def test_translation_preserves_numbers_and_flags_machine_origin(client):
    body = client.post(
        "/v1/translate", json={"text": "तीन लोग फंसे 3 people", "target_language": "en"}
    ).json()
    assert "3" in body["text"] and body["machine_generated"] is True
    assert body["human_verified"] is False
    assert "original text remains" in body["advisory"]


def test_unsupported_language_pair_is_structured(client):
    response = client.post(
        "/v1/translate",
        json={"text": "bonjour", "source_language": "fr", "target_language": "ta"},
    )
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_language_pair"


def test_summary_never_invents_counts_and_never_dispatches(client):
    body = client.post(
        "/v1/summarize",
        json={
            "incidents": [
                {"id": "i1", "people_affected": {"value": 3}},
                {"id": "i2", "people_affected": {"value": None, "raw": "several"}},
            ]
        },
    ).json()
    assert body["estimatedAffectedPeople"]["value"] == 3
    assert body["estimatedAffectedPeople"]["reports_without_count"] == 1
    assert "human review required" in body["advisory"]


def test_empty_cluster_is_rejected(client):
    assert client.post("/v1/summarize", json={"incidents": []}).status_code == 422


def test_every_response_carries_a_request_id(client):
    response = client.post("/v1/triage", json={"text": "fire in the market"})
    assert response.headers["x-request-id"]
    assert float(response.headers["x-elapsed-ms"]) >= 0


def test_openapi_documents_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {
        "/v1/triage",
        "/v1/entities",
        "/v1/transcribe",
        "/v1/embed",
        "/v1/translate",
        "/v1/summarize",
        "/v1/models",
        "/health",
        "/ready",
    } <= set(paths)
