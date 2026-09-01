"""Request and response schemas. Every response carries model version and input hash."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MAX_TEXT_CHARS = 8000


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARS)
    language: str | None = Field(default=None, max_length=8)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class TranscribeRequest(BaseModel):
    audio_base64: str = Field(min_length=1)
    mime_type: str = Field(default="audio/wav", max_length=64)
    language_hint: str | None = Field(default=None, max_length=8)
    duration_s: float | None = Field(default=None, ge=0)


class TranslateRequest(TextRequest):
    target_language: str = Field(min_length=2, max_length=8)
    source_language: str | None = Field(default=None, max_length=8)


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=32)


class SummarizeRequest(BaseModel):
    incidents: list[dict[str, Any]] = Field(min_length=1, max_length=100)
    cluster_id: str | None = None


class ModelStamp(BaseModel):
    name: str
    version: str
    mode: str
    loaded: bool


class ErrorResponse(BaseModel):
    error: str
    detail: str
    request_id: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    mode: str
    service: str = "dms-ai"


class ReadyResponse(BaseModel):
    status: Literal["ready", "degraded"]
    models_loaded: bool
    mode: str
    detail: str
