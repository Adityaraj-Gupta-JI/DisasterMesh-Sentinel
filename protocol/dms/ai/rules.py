"""Deterministic rule inference.

Two jobs: it is the mock model used in development and tests, and it is the real
fallback that runs on-device when no model and no AI service are reachable. The
product must classify and prioritize with nothing but this file available.
"""

from __future__ import annotations

import re

from ..domain.enums import ConditionType, DisasterType, EntityType, Urgency
from .base import (
    EntityResult,
    EntitySpan,
    ModelInfo,
    TriageResult,
    input_hash,
)
from .lexicon import (
    APPROXIMATE_WORDS,
    CONDITION_TERMS,
    DISASTER_TERMS,
    HAZARD_TERMS,
    NUMBER_WORDS,
    RESOURCE_TERMS,
    detect_language,
)

TRIAGE_MODEL = ModelInfo(name="dms-rule-triage", version="1.0.0", mode="mock")
ENTITY_MODEL = ModelInfo(name="dms-rule-entities", version="1.0.0", mode="mock")

#: Phrases that defer an incident regardless of its keywords.
FUTURE_MARKERS = ("tomorrow", "next week", "later today", "कल", "நாளை")


def _found(text_lower: str, term: str) -> bool:
    if term.isascii():
        return re.search(rf"\b{re.escape(term)}\b", text_lower) is not None
    return term in text_lower


def triage(text: str, language: str | None = None) -> TriageResult:
    """Classify urgency, disaster types, and severity from text alone."""
    lang = language or detect_language(text)
    lowered = text.lower()
    types: list[DisasterType] = []
    flags: list[str] = []
    features: list[str] = []
    severity = 0

    for term, (term_types, term_severity, flag) in DISASTER_TERMS.items():
        if _found(lowered, term):
            features.append(f"matched:{term}")
            severity = max(severity, term_severity)
            for t in term_types:
                if t not in types:
                    types.append(t)
            if flag and flag not in flags:
                flags.append(flag)

    deferred = any(marker in lowered for marker in FUTURE_MARKERS)
    if deferred:
        features.append("matched:future_time_reference")
        severity = min(severity, 25)

    if not types:
        types = [DisasterType.OTHER]
        features.append("no_disaster_term_matched")

    if "immediate_life_threat" in flags and not deferred:
        urgency = Urgency.CRITICAL
    elif severity >= 70 and not deferred:
        urgency = Urgency.CRITICAL
    elif severity >= 50:
        urgency = Urgency.HIGH
    elif severity >= 20:
        urgency = Urgency.MEDIUM
    elif severity > 0:
        urgency = Urgency.LOW
    else:
        urgency = Urgency.UNKNOWN

    # Confidence reflects evidence density, never certainty about the world.
    matches = sum(1 for f in features if f.startswith("matched:"))
    confidence = min(0.95, 0.35 + 0.15 * matches) if matches else 0.15

    if DisasterType.LOGISTICS in types and len(types) > 1:
        types = [t for t in types if t is not DisasterType.LOGISTICS]

    return TriageResult(
        urgency=urgency,
        disaster_types=tuple(types),
        severity=severity,
        confidence=round(confidence, 2),
        safety_flags=tuple(flags),
        explanation_features=tuple(features + [f"language:{lang}"]),
        model=TRIAGE_MODEL,
        input_hash=input_hash(text),
    )


#: Nouns that mark a number as a count of people rather than an unrelated quantity.
PEOPLE_NOUNS = (
    "people",
    "person",
    "persons",
    "men",
    "women",
    "children",
    "kids",
    "victims",
    "लोग",
    "व्यक्ति",
    "बच्चे",
    "நபர்",
    "பேர்",
    "குழந்தை",
)


def _people_nearby(text_lower: str, end: int, window: int = 24) -> bool:
    """True when a people noun follows the number closely enough to bind to it."""
    tail = text_lower[end : end + window]
    return any(noun in tail for noun in PEOPLE_NOUNS)


def _people_quantity(text: str) -> tuple[dict, list[EntitySpan]]:
    """Extract a people count.

    Two rules matter more than recall here:
      * a number bound to a people noun beats a bare number elsewhere in the text
        ("Three people trapped, one bleeding" is three, not one);
      * a vague word never becomes a number.
    """
    lowered = text.lower()
    spans: list[EntitySpan] = []
    candidates: list[tuple[bool, int, int, str, int, int]] = []

    for word, value in NUMBER_WORDS.items():
        pattern = rf"\b{re.escape(word)}\b" if word.isascii() else re.escape(word)
        for m in re.finditer(pattern, lowered):
            candidates.append(
                (
                    _people_nearby(lowered, m.end()),
                    m.start(),
                    value,
                    text[m.start() : m.end()],
                    m.start(),
                    m.end(),
                )
            )

    for m in re.finditer(r"\b(\d{1,4})\b", lowered):
        candidates.append(
            (
                _people_nearby(lowered, m.end()),
                m.start(),
                int(m.group(1)),
                m.group(0),
                m.start(),
                m.end(),
            )
        )

    if candidates:
        # Prefer a number bound to a people noun; among equals, the earliest one.
        bound, _pos, value, raw, start, end = sorted(candidates, key=lambda c: (not c[0], c[1]))[0]
        confidence = 0.92 if bound else 0.6
        spans.append(
            EntitySpan(
                type=EntityType.PEOPLE_COUNT,
                raw=raw,
                value=value,
                confidence=confidence,
                uncertain=not bound,
                start=start,
                end=end,
            )
        )
        return (
            {"value": value, "raw": raw, "confidence": confidence, "approximate": False},
            spans,
        )

    for word in APPROXIMATE_WORDS:
        pattern = rf"\b{re.escape(word)}\b" if word.isascii() else re.escape(word)
        m = re.search(pattern, lowered)
        if m:
            raw = text[m.start() : m.end()]
            spans.append(
                EntitySpan(
                    type=EntityType.PEOPLE_COUNT,
                    raw=raw,
                    value=None,
                    confidence=0.5,
                    uncertain=True,
                    start=m.start(),
                    end=m.end(),
                )
            )
            # Deliberately no numeric value: an approximate word is not a count.
            return {"value": None, "raw": raw, "confidence": 0.5, "approximate": True}, spans

    return {"value": None, "raw": None, "confidence": 0.0, "approximate": True}, spans


def extract_entities(text: str, language: str | None = None) -> EntityResult:
    """Pull normalized emergency entities while preserving every raw span."""
    lowered = text.lower()
    people, spans = _people_quantity(text)

    conditions: list[dict] = []
    seen: set[ConditionType] = set()
    for term, ctype in CONDITION_TERMS.items():
        if _found(lowered, term) and ctype not in seen:
            seen.add(ctype)
            conditions.append({"type": ctype.value, "raw": term, "confidence": 0.9})
            spans.append(
                EntitySpan(type=EntityType.CONDITION, raw=term, value=ctype.value, confidence=0.9)
            )

    resources: list[str] = []
    for term, kind in RESOURCE_TERMS.items():
        if _found(lowered, term) and kind not in resources:
            resources.append(kind)
            spans.append(
                EntitySpan(type=EntityType.RESOURCE_REQUEST, raw=term, value=kind, confidence=0.8)
            )

    hazards = []
    for term in HAZARD_TERMS:
        if _found(lowered, term) and term not in hazards:
            hazards.append(term)
            spans.append(EntitySpan(type=EntityType.HAZARD, raw=term, confidence=0.75))

    hints = re.findall(r"\b(?:near|behind|opposite|at)\s+([A-Za-z][\w\s]{2,24}?)(?:[.,]|$)", text)
    location_hints = [h.strip() for h in hints][:3]
    for h in location_hints:
        spans.append(EntitySpan(type=EntityType.LOCATION_HINT, raw=h, confidence=0.6))

    return EntityResult(
        people_affected=people,
        conditions=tuple(conditions),
        resources=tuple(resources),
        hazards=tuple(hazards),
        location_hints=tuple(location_hints),
        spans=tuple(spans),
        model=ENTITY_MODEL,
        input_hash=input_hash(text),
    )
