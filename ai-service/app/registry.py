"""Versioned model registry.

Every endpoint answers with the exact model name, version, and mode that produced the
result, so a coordinator's decision can always be traced back to an inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import settings


@dataclass(frozen=True)
class RegisteredModel:
    task: str
    name: str
    version: str
    mode: str
    loaded: bool
    checkpoint: str | None = None
    languages: tuple[str, ...] = ("en", "hi", "ta")

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "name": self.name,
            "version": self.version,
            "mode": self.mode,
            "loaded": self.loaded,
            "checkpoint": self.checkpoint,
            "languages": list(self.languages),
        }


def registry() -> list[RegisteredModel]:
    """What is actually available right now — never an aspirational list."""
    s = settings
    return [
        RegisteredModel(
            "transcribe",
            "whisper-mock" if not s.enable_whisper else "whisper",
            "1.0.0",
            "real" if s.enable_whisper else "mock",
            loaded=not s.enable_whisper,
            checkpoint=s.whisper_checkpoint if s.enable_whisper else None,
        ),
        RegisteredModel(
            "triage",
            "dms-rule-triage" if not s.enable_triage_model else "xlm-r-triage",
            "1.0.0",
            "real" if s.enable_triage_model else "mock",
            loaded=not s.enable_triage_model,
            checkpoint=s.triage_checkpoint if s.enable_triage_model else None,
        ),
        RegisteredModel(
            "entities",
            "dms-rule-entities" if not s.enable_entity_model else "mdeberta-ner",
            "1.0.0",
            "real" if s.enable_entity_model else "mock",
            loaded=not s.enable_entity_model,
            checkpoint=s.entity_checkpoint if s.enable_entity_model else None,
        ),
        RegisteredModel(
            "embed",
            "multilingual-e5-mock" if not s.enable_embeddings else "multilingual-e5",
            "1.0.0",
            "real" if s.enable_embeddings else "mock",
            loaded=not s.enable_embeddings,
            checkpoint=s.embedding_checkpoint if s.enable_embeddings else None,
        ),
        RegisteredModel(
            "translate",
            "nllb-mock" if not s.enable_translation else "nllb-200",
            "1.0.0",
            "real" if s.enable_translation else "mock",
            loaded=not s.enable_translation,
            checkpoint=s.translation_checkpoint if s.enable_translation else None,
        ),
        RegisteredModel("summarize", "summary-mock", "1.0.0", "mock", loaded=True),
    ]


def models_loaded() -> bool:
    """Readiness: a real model that is enabled but not loaded means not ready."""
    return all(m.loaded for m in registry())
