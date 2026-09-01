"""Mock adapters for transcription, embeddings, translation, and summarization.

Deterministic by construction so tests never flake. Each stands in for a real model
behind the same interface: Whisper, multilingual-e5, NLLB, and a summarization LLM.
"""

from __future__ import annotations

import hashlib
import math
import re

from .base import (
    AIError,
    EmbeddingResult,
    ModelInfo,
    SummaryResult,
    TranscriptResult,
    TranscriptSegment,
    TranslationResult,
    input_hash,
)
from .lexicon import detect_language

WHISPER_MOCK = ModelInfo(name="whisper-mock", version="1.0.0", mode="mock")
EMBED_MOCK = ModelInfo(name="multilingual-e5-mock", version="1.0.0", mode="mock")
TRANSLATE_MOCK = ModelInfo(name="nllb-mock", version="1.0.0", mode="mock")
SUMMARY_MOCK = ModelInfo(name="summary-mock", version="1.0.0", mode="mock")

SUPPORTED_AUDIO_MIME = frozenset(
    {"audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/ogg"}
)
MAX_AUDIO_SECONDS = 300
EMBED_DIM = 64

#: Fixture transcripts keyed by the first bytes of the audio, so a test can ask for a
#: specific language without shipping real audio.
FIXTURE_TRANSCRIPTS: dict[str, tuple[str, str]] = {
    "EN": ("en", "Three people trapped under collapsed building near market road"),
    "HI": ("hi", "तीन लोग गिरी हुई इमारत में फंसे हैं"),
    "TA": ("ta", "மூன்று பேர் இடிந்த கட்டிடத்தில் சிக்கியுள்ளனர்"),
    "MX": ("hi", "building collapse हुआ है, तीन लोग trapped हैं"),
}


def transcribe(
    audio: bytes,
    *,
    mime_type: str,
    language_hint: str | None = None,
    duration_s: float | None = None,
) -> TranscriptResult:
    """Mock multilingual transcription. Validates before it pretends to listen."""
    if mime_type not in SUPPORTED_AUDIO_MIME:
        raise AIError("unsupported_media_type", f"unsupported audio MIME type {mime_type!r}")
    if not audio:
        raise AIError("empty_audio", "audio payload is empty")
    if duration_s is not None and duration_s > MAX_AUDIO_SECONDS:
        raise AIError("audio_too_long", f"audio {duration_s}s exceeds {MAX_AUDIO_SECONDS}s")

    audio_sha = hashlib.sha256(audio).hexdigest()
    marker = audio[:2].decode("ascii", errors="ignore").upper()
    language, text = FIXTURE_TRANSCRIPTS.get(marker, ("und", ""))
    if language_hint and marker not in FIXTURE_TRANSCRIPTS:
        language = language_hint

    low_quality = not text
    segments = (TranscriptSegment(start_s=0.0, end_s=duration_s or 3.0, text=text),) if text else ()
    return TranscriptResult(
        text=text,
        language=language,
        segments=segments,
        audio_sha256=audio_sha,
        machine_generated=True,
        low_quality=low_quality,
        confidence=None if low_quality else 0.82,
        model=WHISPER_MOCK,
        input_hash=audio_sha,
    )


def embed(text: str) -> EmbeddingResult:
    """Deterministic bag-of-words hashing embedding, L2-normalized.

    Cross-language matching works because the shared lexicon maps equivalent terms to
    a canonical token before hashing.
    """
    from .lexicon import CONDITION_TERMS, DISASTER_TERMS

    canonical: list[str] = []
    lowered = text.lower()
    for term, (types, _sev, _flag) in DISASTER_TERMS.items():
        if term in lowered:
            canonical.extend(t.value for t in types)
    for term, ctype in CONDITION_TERMS.items():
        if term in lowered:
            canonical.append(ctype.value)
    canonical.extend(re.findall(r"[a-z]{4,}", lowered))

    vector = [0.0] * EMBED_DIM
    for token in canonical or ["EMPTY"]:
        idx = int(hashlib.blake2b(token.encode("utf-8"), digest_size=4).hexdigest(), 16) % EMBED_DIM
        vector[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return EmbeddingResult(
        vector=tuple(v / norm for v in vector), model=EMBED_MOCK, input_hash=input_hash(text)
    )


def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


#: Minimal glossary so the mock produces recognizably translated output.
_GLOSS = {
    ("hi", "en"): {
        "तीन": "three",
        "लोग": "people",
        "फंसे": "trapped",
        "इमारत": "building",
        "आग": "fire",
        "बाढ़": "flood",
        "मदद": "help",
        "पानी": "water",
        "घायल": "injured",
    },
    ("ta", "en"): {
        "மூன்று": "three",
        "பேர்": "people",
        "சிக்கி": "trapped",
        "கட்டிடம்": "building",
        "தீ": "fire",
        "வெள்ளம்": "flood",
        "உதவி": "help",
        "தண்ணீர்": "water",
    },
    ("en", "ta"): {
        "three": "மூன்று",
        "people": "பேர்",
        "trapped": "சிக்கி",
        "fire": "தீ",
        "flood": "வெள்ளம்",
        "help": "உதவி",
        "water": "தண்ணீர்",
    },
    ("en", "hi"): {
        "three": "तीन",
        "people": "लोग",
        "trapped": "फंसे",
        "fire": "आग",
        "flood": "बाढ़",
        "help": "मदद",
        "water": "पानी",
    },
}

#: Tokens that must survive translation byte-for-byte.
_PRESERVE = re.compile(r"(\d+(?:\.\d+)?|inc_[a-z0-9]+|[A-Z]{2,}\d+|\d+\.\d+,\s*\d+\.\d+)")


def translate(
    text: str, *, target_language: str, source_language: str | None = None
) -> TranslationResult:
    """Mock translation that provably preserves numbers, ids, and coordinates."""
    source = source_language or detect_language(text)
    if source == target_language:
        preserved = tuple(_PRESERVE.findall(text))
        return TranslationResult(
            text=text,
            source_language=source,
            target_language=target_language,
            machine_generated=True,
            human_verified=False,
            preserved_tokens=preserved,
            model=TRANSLATE_MOCK,
            input_hash=input_hash(text),
        )
    gloss = _GLOSS.get((source, target_language))
    if gloss is None:
        raise AIError(
            "unsupported_language_pair", f"no translation model for {source}->{target_language}"
        )
    preserved = tuple(_PRESERVE.findall(text))
    out = text
    for src_term, dst_term in gloss.items():
        out = out.replace(src_term, dst_term)
    for token in preserved:
        if token not in out:  # a substitution ate a protected token — restore it
            out = f"{out} {token}"
    return TranslationResult(
        text=out,
        source_language=source,
        target_language=target_language,
        machine_generated=True,
        human_verified=False,
        preserved_tokens=preserved,
        model=TRANSLATE_MOCK,
        input_hash=input_hash(text),
    )


def summarize(incidents: list[dict], *, cluster_id: str | None = None) -> SummaryResult:
    """Aggregate a cluster without inventing anything.

    Counts are summed only from reports that state an exact number; anything vague is
    surfaced as an uncertainty instead of being folded into the total.
    """
    if not incidents:
        raise AIError("empty_cluster", "cannot summarize an empty cluster")

    ids = tuple(i.get("id", "") for i in incidents)
    exact_total = 0
    exact_sources = 0
    unknown_sources = 0
    hazards: list[str] = []
    resources: list[str] = []
    facts: list[str] = []
    uncertainties: list[str] = []

    for inc in incidents:
        people = inc.get("people_affected") or {}
        value = people.get("value")
        if isinstance(value, int):
            exact_total += value
            exact_sources += 1
            facts.append(f"{inc.get('id')}: reports {value} people affected")
        else:
            unknown_sources += 1
            raw = people.get("raw")
            uncertainties.append(
                f"{inc.get('id')}: people count not stated" + (f" (raw: {raw!r})" if raw else "")
            )
        for h in inc.get("hazards", []) or []:
            if h not in hazards:
                hazards.append(h)
        for r in inc.get("requested_resources", []) or []:
            if r not in resources:
                resources.append(r)
        text = (inc.get("original_text") or "").strip()
        if text:
            facts.append(f'{inc.get("id")}: reported "{text[:80]}"')

    types: list[str] = []
    for inc in incidents:
        for t in inc.get("disaster_types", []) or []:
            if t not in types:
                types.append(t)

    if unknown_sources:
        uncertainties.append(
            f"{unknown_sources} of {len(incidents)} reports give no exact count; "
            f"the estimate covers only the {exact_sources} that do"
        )
    conflicting = {i.get("people_affected", {}).get("value") for i in incidents} - {None}
    if len(conflicting) > 1:
        uncertainties.append(f"reports disagree on people affected: {sorted(conflicting)}")

    return SummaryResult(
        situation_summary=(
            f"{len(incidents)} report(s) in cluster {cluster_id or 'unclustered'} "
            f"covering {', '.join(types) or 'unclassified'}."
        ),
        confirmed_facts=tuple(facts),
        estimated_affected_people={
            "value": exact_total if exact_sources else None,
            "basis": f"sum of {exact_sources} report(s) stating an exact count",
            "reports_without_count": unknown_sources,
        },
        active_hazards=tuple(hazards),
        required_resources=tuple(resources),
        uncertainties=tuple(uncertainties),
        recommended_human_actions=(
            "Coordinator to verify counts with the reporting nodes",
            "Coordinator to decide dispatch — this summary never dispatches",
        ),
        source_incident_ids=ids,
        model=SUMMARY_MOCK,
        input_hash=input_hash(str(sorted(ids))),
    )
