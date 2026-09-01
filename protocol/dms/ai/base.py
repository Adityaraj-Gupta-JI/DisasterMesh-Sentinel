"""AI adapter contracts.

Every result carries a model name, a model version, and a hash of the input, so any
downstream decision can be traced back to the exact inference that informed it.
Nothing in this package decides anything: results are recommendations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..domain.enums import DisasterType, EntityType, Provenance, Urgency
from ..protocol.bundle import sha256_hex

MAX_TEXT_BYTES = 32 * 1024
MAX_AUDIO_BYTES = 16 * 1024 * 1024


def input_hash(data: str | bytes) -> str:
    return sha256_hex(data.encode("utf-8") if isinstance(data, str) else data)


@dataclass(frozen=True)
class ModelInfo:
    name: str
    version: str
    mode: str = "mock"  # "mock" | "real"
    loaded: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "mode": self.mode,
            "loaded": self.loaded,
        }


@dataclass(frozen=True)
class TriageResult:
    urgency: Urgency
    disaster_types: tuple[DisasterType, ...]
    severity: int
    confidence: float
    safety_flags: tuple[str, ...]
    explanation_features: tuple[str, ...]
    model: ModelInfo
    input_hash: str
    provenance: Provenance = Provenance.MACHINE_GENERATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "urgency": self.urgency.value,
            "disaster_types": [d.value for d in self.disaster_types],
            "severity": self.severity,
            "confidence": self.confidence,
            "safety_flags": list(self.safety_flags),
            "explanation_features": list(self.explanation_features),
            "model": self.model.to_dict(),
            "input_hash": self.input_hash,
            "provenance": self.provenance.value,
        }


@dataclass(frozen=True)
class EntitySpan:
    type: EntityType
    raw: str
    value: str | int | None = None
    confidence: float = 0.0
    uncertain: bool = False
    start: int | None = None
    end: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "raw": self.raw,
            "value": self.value,
            "confidence": self.confidence,
            "uncertain": self.uncertain,
            "start": self.start,
            "end": self.end,
        }


@dataclass(frozen=True)
class EntityResult:
    people_affected: dict[str, Any]
    conditions: tuple[dict[str, Any], ...]
    resources: tuple[str, ...]
    hazards: tuple[str, ...]
    location_hints: tuple[str, ...]
    spans: tuple[EntitySpan, ...]
    model: ModelInfo
    input_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "peopleAffected": self.people_affected,
            "conditions": list(self.conditions),
            "resources": list(self.resources),
            "hazards": list(self.hazards),
            "locationHints": list(self.location_hints),
            "spans": [s.to_dict() for s in self.spans],
            "model": self.model.to_dict(),
            "input_hash": self.input_hash,
        }


@dataclass(frozen=True)
class TranscriptSegment:
    start_s: float
    end_s: float
    text: str


@dataclass(frozen=True)
class TranscriptResult:
    text: str
    language: str
    segments: tuple[TranscriptSegment, ...]
    audio_sha256: str
    machine_generated: bool
    low_quality: bool
    confidence: float | None
    model: ModelInfo
    input_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "segments": [
                {"start_s": s.start_s, "end_s": s.end_s, "text": s.text} for s in self.segments
            ],
            "audio_sha256": self.audio_sha256,
            "machine_generated": self.machine_generated,
            "low_quality": self.low_quality,
            "confidence": self.confidence,
            "model": self.model.to_dict(),
            "input_hash": self.input_hash,
        }


@dataclass(frozen=True)
class TranslationResult:
    text: str
    source_language: str
    target_language: str
    machine_generated: bool
    human_verified: bool
    preserved_tokens: tuple[str, ...]
    model: ModelInfo
    input_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "machine_generated": self.machine_generated,
            "human_verified": self.human_verified,
            "preserved_tokens": list(self.preserved_tokens),
            "model": self.model.to_dict(),
            "input_hash": self.input_hash,
        }


@dataclass(frozen=True)
class EmbeddingResult:
    vector: tuple[float, ...]
    model: ModelInfo
    input_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "vector": list(self.vector),
            "model": self.model.to_dict(),
            "input_hash": self.input_hash,
        }


@dataclass(frozen=True)
class SummaryResult:
    situation_summary: str
    confirmed_facts: tuple[str, ...]
    estimated_affected_people: dict[str, Any]
    active_hazards: tuple[str, ...]
    required_resources: tuple[str, ...]
    uncertainties: tuple[str, ...]
    recommended_human_actions: tuple[str, ...]
    source_incident_ids: tuple[str, ...]
    model: ModelInfo
    input_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "situationSummary": self.situation_summary,
            "confirmedFacts": list(self.confirmed_facts),
            "estimatedAffectedPeople": self.estimated_affected_people,
            "activeHazards": list(self.active_hazards),
            "requiredResources": list(self.required_resources),
            "uncertainties": list(self.uncertainties),
            "recommendedHumanActions": list(self.recommended_human_actions),
            "sourceIncidentIds": list(self.source_incident_ids),
            "modelVersion": self.model.version,
            "input_hash": self.input_hash,
        }


class AIError(Exception):
    """Structured inference failure. Callers fall back to rules and keep going."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"error": self.code, "detail": self.message}


class TriageModel(Protocol):
    def triage(self, text: str, language: str | None = None) -> TriageResult: ...
