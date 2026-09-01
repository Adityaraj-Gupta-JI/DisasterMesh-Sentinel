"""AI service configuration.

Mock mode is the default and is a first-class mode, not a stub: it is what runs when
no model weights are present, and it is the behavior the mesh degrades to.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    mode: str = field(default_factory=lambda: os.getenv("DMS_AI_MODE", "mock"))
    request_timeout_s: float = field(
        default_factory=lambda: float(os.getenv("DMS_AI_TIMEOUT_S", "10"))
    )
    max_text_bytes: int = 32 * 1024
    max_audio_bytes: int = 16 * 1024 * 1024
    max_batch: int = 32
    log_payloads: bool = field(default_factory=lambda: _flag("DMS_AI_LOG_PAYLOADS", False))

    # Real models load only when explicitly enabled AND a checkpoint is configured.
    enable_whisper: bool = field(default_factory=lambda: _flag("DMS_AI_ENABLE_WHISPER"))
    enable_triage_model: bool = field(default_factory=lambda: _flag("DMS_AI_ENABLE_TRIAGE"))
    enable_entity_model: bool = field(default_factory=lambda: _flag("DMS_AI_ENABLE_ENTITIES"))
    enable_embeddings: bool = field(default_factory=lambda: _flag("DMS_AI_ENABLE_EMBEDDINGS"))
    enable_translation: bool = field(default_factory=lambda: _flag("DMS_AI_ENABLE_TRANSLATION"))

    whisper_checkpoint: str = field(
        default_factory=lambda: os.getenv("DMS_AI_WHISPER_CKPT", "openai/whisper-small")
    )
    triage_checkpoint: str = field(
        default_factory=lambda: os.getenv("DMS_AI_TRIAGE_CKPT", "xlm-roberta-base")
    )
    entity_checkpoint: str = field(
        default_factory=lambda: os.getenv("DMS_AI_ENTITY_CKPT", "microsoft/mdeberta-v3-base")
    )
    embedding_checkpoint: str = field(
        default_factory=lambda: os.getenv("DMS_AI_EMBED_CKPT", "intfloat/multilingual-e5-large")
    )
    translation_checkpoint: str = field(
        default_factory=lambda: os.getenv(
            "DMS_AI_TRANSLATE_CKPT", "facebook/nllb-200-distilled-600M"
        )
    )

    @property
    def any_real_model_enabled(self) -> bool:
        return any(
            [
                self.enable_whisper,
                self.enable_triage_model,
                self.enable_entity_model,
                self.enable_embeddings,
                self.enable_translation,
            ]
        )


settings = Settings()
