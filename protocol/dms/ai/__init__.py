"""One place to pick which triage model is active.

Both `backend/app/main.py` (`_classify_text`) and `ai-service/app/main.py`
(`/v1/triage`) previously imported `dms.ai.rules.triage` directly and
separately — this factory is the single switch so the mode is controlled in
exactly one place, read fresh on every call (not cached at import time), so
tests can flip `DMS_AI_MODE` per-test via `monkeypatch.setenv`.
"""

from __future__ import annotations

import os

from .base import TriageModel


def get_triage_model() -> TriageModel:
    mode = os.getenv("DMS_AI_MODE", "mock")
    if mode == "llm":
        from .llm import FallbackTriageModel

        return FallbackTriageModel()

    from . import rules

    return rules
