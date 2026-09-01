"""API schemas. Validation happens here so handlers stay small."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from dms.domain.enums import (
    AttachmentKind,
    DispatchStatus,
    IncidentStatus,
    PriorityClass,
    ResourceKind,
)
from pydantic import BaseModel, Field, field_validator

MAX_TEXT = 8000
ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/ogg",
    "audio/webm",  # MediaRecorder's default output in Chromium browsers
    "application/pdf",
    "text/plain",
}


class IncidentCreate(BaseModel):
    id: str | None = None
    source_node_id: str = Field(min_length=1, max_length=64)
    original_text: str = Field(min_length=1, max_length=MAX_TEXT)
    source_language: str = Field(default="und", max_length=8)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_accuracy_m: float | None = Field(default=None, ge=0)
    reported_at: datetime | None = None
    disaster_types: list[str] = Field(default_factory=list, max_length=8)
    urgency: str = "UNKNOWN"
    severity: int = Field(default=0, ge=0, le=100)
    priority_class: PriorityClass = PriorityClass.P3
    priority_score: int = Field(default=0, ge=0, le=100)
    people_affected: dict[str, Any] | None = None
    conditions: list[dict[str, Any]] = Field(default_factory=list, max_length=16)
    sensitivity: str = "OPERATIONAL"
    revision: int = Field(default=1, ge=1)
    priority_explanation: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("original_text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("original_text must not be blank")
        return value


class IncidentOut(BaseModel):
    id: str
    organization_id: str
    source_node_id: str
    original_text: str
    source_language: str
    status: IncidentStatus
    priority_class: PriorityClass
    priority_score: int
    severity: int
    urgency: str
    sensitivity: str
    verification_status: str
    revision: int
    cluster_id: str | None = None
    reported_at: datetime
    updated_at: datetime
    doc: dict[str, Any]


class Page(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


class AcknowledgeRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=500)


class IncidentNoteCreate(BaseModel):
    """A durable coordinator note — typed, or transcribed-then-reviewed voice.

    The transcription itself is never trusted blindly: the dashboard shows it
    in an editable box first, so `text` here is always what a human confirmed,
    not raw model output.
    """

    text: str = Field(min_length=1, max_length=MAX_TEXT)
    source: Literal["text", "voice"] = "text"
    audio_attachment_id: str | None = None

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class IncidentNoteOut(BaseModel):
    id: str
    incident_id: str
    author_user_id: str | None = None
    text: str
    source: str
    audio_attachment_id: str | None = None
    created_at: datetime


class StatusUpdate(BaseModel):
    status: IncidentStatus
    reason: str | None = Field(default=None, max_length=500)


class AttachmentCreate(BaseModel):
    id: str | None = None
    file_name: str = Field(min_length=1, max_length=200)
    mime_type: str = Field(min_length=1, max_length=100)
    size_bytes: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    kind: AttachmentKind = AttachmentKind.IMAGE
    verified: bool = False
    # Optional base64 of the file itself. When present the gateway stores the bytes
    # so the dashboard can render them; when absent, behaviour is exactly as before
    # (metadata only). Backward compatible with every existing caller.
    data_base64: str | None = None

    @field_validator("mime_type")
    @classmethod
    def allowed(cls, value: str) -> str:
        if value not in ALLOWED_MIME:
            raise ValueError(f"MIME type {value} is not permitted")
        return value

    @field_validator("sha256")
    @classmethod
    def hexadecimal(cls, value: str) -> str:
        int(value, 16)  # raises ValueError when not hex
        return value.lower()


class TranscribeRequest(BaseModel):
    """Audio to be turned into text by the existing speech-to-text pipeline."""

    audio_base64: str = Field(min_length=1)
    mime_type: str = Field(default="audio/wav", max_length=100)
    language_hint: str | None = Field(default=None, max_length=8)
    duration_s: float | None = Field(default=None, ge=0)

    @field_validator("mime_type")
    @classmethod
    def audio_only(cls, value: str) -> str:
        if not value.startswith("audio/"):
            raise ValueError("mime_type must be an audio type")
        return value


class ComposeRequest(BaseModel):
    """Free text (typed, or transcribed from audio) to classify and file as an
    incident through the same pipeline any client uses."""

    text: str = Field(min_length=1, max_length=MAX_TEXT)
    source_node_id: str = Field(default="dashboard", min_length=1, max_length=64)
    source_language: str | None = Field(default=None, max_length=8)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank")
        return value


class ResourceCreate(BaseModel):
    id: str | None = None
    kind: ResourceKind
    label: str = Field(min_length=1, max_length=100)
    status: str = "AVAILABLE"
    capabilities: list[str] = Field(default_factory=list, max_length=12)
    simulated: Literal[True] = True  # a non-simulated resource cannot be represented


class DispatchCreate(BaseModel):
    incident_id: str
    resource_id: str
    reason: str = Field(min_length=1, max_length=500)


class DispatchAdvance(BaseModel):
    status: DispatchStatus


class AlertCreate(BaseModel):
    headline: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    incident_ids: list[str] = Field(default_factory=list, max_length=50)
    confirm: bool = Field(description="explicit human confirmation is mandatory")

    @field_validator("confirm")
    @classmethod
    def must_confirm(cls, value: bool) -> bool:
        if not value:
            raise ValueError("a public alert requires explicit confirmation")
        return value


class SyncPush(BaseModel):
    node_id: str = Field(min_length=1, max_length=64)
    incidents: list[IncidentCreate] = Field(default_factory=list, max_length=200)


class NodeHeartbeat(BaseModel):
    node_id: str = Field(min_length=1, max_length=64)
    role: str = "CITIZEN_REPORTER"
    battery_percent: int = Field(default=100, ge=0, le=100)
    nearby_peers: int = Field(default=0, ge=0)
    stored_bundles: int = Field(default=0, ge=0)

