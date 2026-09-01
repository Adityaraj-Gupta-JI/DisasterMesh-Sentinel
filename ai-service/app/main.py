"""DisasterMesh AI inference service.

Contract with the rest of the system:
  * every response carries a model version and an input hash;
  * failures are structured, so callers fall back to rules and keep working;
  * nothing here dispatches a resource or publishes an alert;
  * raw report text is never written to normal logs.
"""

from __future__ import annotations

import base64
import binascii
import logging
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "protocol"))

from dms.ai import get_triage_model, mocks  # noqa: E402
from dms.ai.base import AIError  # noqa: E402
from dms.ai.rules import extract_entities  # noqa: E402

from .config import settings  # noqa: E402
from .registry import models_loaded, registry  # noqa: E402
from .schemas import (  # noqa: E402
    EmbedRequest,
    ErrorResponse,
    HealthResponse,
    ReadyResponse,
    SummarizeRequest,
    TextRequest,
    TranscribeRequest,
    TranslateRequest,
)

logger = logging.getLogger("dms.ai")

app = FastAPI(
    title="DisasterMesh Sentinel AI Service",
    version="1.0.0",
    description=(
        "Inference for emergency triage, extraction, transcription, embeddings, "
        "translation, and cluster summarization. All outputs are recommendations."
    ),
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request id and timing. Never logs the payload itself."""
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled error request_id=%s path=%s", request_id, request.url.path)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error", detail="inference failed", request_id=request_id
            ).model_dump(),
        )
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["x-request-id"] = request_id
    response.headers["x-elapsed-ms"] = f"{elapsed_ms:.1f}"
    logger.info(
        "request_id=%s path=%s status=%s ms=%.1f",
        request_id,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


def _ai_error(exc: AIError, status: int = 422) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=ErrorResponse(error=exc.code, detail=exc.message).model_dump()
    )


# ------------------------------------------------------------------- health


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness only: the process is up. Says nothing about model state."""
    return HealthResponse(status="ok", mode=settings.mode)


@app.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    """Readiness: distinguishes 'service up' from 'models loaded'."""
    loaded = models_loaded()
    return ReadyResponse(
        status="ready" if loaded else "degraded",
        models_loaded=loaded,
        mode=settings.mode,
        detail=(
            "all configured models are available"
            if loaded
            else "a real model is enabled but not loaded; callers must fall back to rules"
        ),
    )


@app.get("/v1/models")
def list_models() -> dict:
    return {"models": [m.to_dict() for m in registry()], "mode": settings.mode}


# ------------------------------------------------------------------ inference


@app.post("/v1/triage")
def post_triage(request: TextRequest):
    """Classify urgency, disaster types, and severity. A recommendation only."""
    result = get_triage_model().triage(request.text, request.language)
    return result.to_dict() | {"advisory": "recommendation_only_not_a_dispatch"}


@app.post("/v1/entities")
def post_entities(request: TextRequest):
    """Extract emergency entities, preserving every raw span."""
    return extract_entities(request.text, request.language).to_dict()


@app.post("/v1/transcribe")
def post_transcribe(request: TranscribeRequest):
    """Multilingual transcription. The original audio is never modified or deleted."""
    try:
        audio = base64.b64decode(request.audio_base64, validate=True)
    except (binascii.Error, ValueError):
        return _ai_error(AIError("invalid_base64", "audio_base64 is not valid base64"), 400)
    if len(audio) > settings.max_audio_bytes:
        return _ai_error(
            AIError("audio_too_large", f"audio exceeds {settings.max_audio_bytes} bytes"), 413
        )
    try:
        result = mocks.transcribe(
            audio,
            mime_type=request.mime_type,
            language_hint=request.language_hint,
            duration_s=request.duration_s,
        )
    except AIError as exc:
        return _ai_error(exc)
    return result.to_dict()


@app.post("/v1/embed")
def post_embed(request: EmbedRequest):
    results = [mocks.embed(text) for text in request.texts]
    return {
        "embeddings": [r.to_dict() for r in results],
        "dimension": len(results[0].vector),
        "model": results[0].model.to_dict(),
    }


@app.post("/v1/translate")
def post_translate(request: TranslateRequest):
    """Translate for comprehension. The original text always remains authoritative."""
    try:
        result = mocks.translate(
            request.text,
            target_language=request.target_language,
            source_language=request.source_language,
        )
    except AIError as exc:
        return _ai_error(exc)
    return result.to_dict() | {
        "advisory": "machine translation; the original text remains the source of record"
    }


@app.post("/v1/summarize")
def post_summarize(request: SummarizeRequest):
    """Summarize a cluster without inventing facts or issuing orders."""
    try:
        result = mocks.summarize(request.incidents, cluster_id=request.cluster_id)
    except AIError as exc:
        return _ai_error(exc)
    return result.to_dict() | {"advisory": "no dispatch authority; human review required"}
