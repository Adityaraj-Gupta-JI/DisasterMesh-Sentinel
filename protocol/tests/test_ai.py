"""AI adapters: multilingual rules, mocks, and the guarantees around them."""

from __future__ import annotations

import pytest
from dms.ai import mocks
from dms.ai.base import AIError
from dms.ai.lexicon import detect_language
from dms.ai.rules import extract_entities, triage
from dms.domain.enums import ConditionType, DisasterType, Urgency

# ----------------------------------------------------------------- triage


def test_collapse_report_is_critical_with_life_threat_flag():
    r = triage("Three people trapped under collapsed building")
    assert r.urgency is Urgency.CRITICAL
    assert DisasterType.BUILDING_COLLAPSE in r.disaster_types
    assert DisasterType.TRAPPED_PERSON in r.disaster_types
    assert "immediate_life_threat" in r.safety_flags
    assert r.severity >= 70


def test_future_water_request_is_not_critical():
    r = triage("Need drinking water at shelter tomorrow")
    assert r.urgency in (Urgency.MEDIUM, Urgency.LOW)
    assert DisasterType.LOGISTICS in r.disaster_types or DisasterType.OTHER in r.disaster_types
    assert "immediate_life_threat" not in r.safety_flags


@pytest.mark.parametrize(
    "text,lang",
    [
        ("Three people trapped under collapsed building", "en"),
        ("तीन लोग गिरी हुई इमारत में फंसे हैं", "hi"),
        ("மூன்று பேர் இடிந்த கட்டிடத்தில் சிக்கியுள்ளனர்", "ta"),
    ],
)
def test_multilingual_triage_reaches_the_same_verdict(text, lang):
    r = triage(text)
    assert detect_language(text) == lang
    assert r.urgency is Urgency.CRITICAL
    assert DisasterType.TRAPPED_PERSON in r.disaster_types


def test_code_switched_input_is_classified():
    r = triage("building collapse हुआ है, तीन लोग trapped हैं")
    assert r.urgency is Urgency.CRITICAL
    assert DisasterType.TRAPPED_PERSON in r.disaster_types


def test_triage_carries_model_version_and_input_hash():
    r = triage("fire in the market")
    assert r.model.version and r.model.name
    assert len(r.input_hash) == 64


def test_triage_is_deterministic():
    assert triage("flood near the bridge").to_dict() == triage("flood near the bridge").to_dict()


def test_unclassifiable_text_is_low_confidence_not_a_guess():
    r = triage("hello there")
    assert r.urgency is Urgency.UNKNOWN
    assert r.confidence < 0.3


# --------------------------------------------------------------- entities


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Three people trapped", 3),
        ("3 people trapped", 3),
        ("तीन लोग फंसे हैं", 3),
        ("மூன்று பேர் சிக்கியுள்ளனர்", 3),
        ("Three people trapped, one bleeding", 3),
    ],
)
def test_exact_people_counts_are_extracted(text, expected):
    assert extract_entities(text).people_affected["value"] == expected


@pytest.mark.parametrize("text", ["Some people are trapped", "कुछ लोग फंसे हैं", "பல பேர் சிக்கி"])
def test_vague_quantities_never_become_numbers(text):
    people = extract_entities(text).people_affected
    assert people["value"] is None
    assert people["approximate"] is True
    assert people["raw"], "the vague phrase itself must be preserved"


def test_absent_count_is_unknown():
    people = extract_entities("Building is on fire").people_affected
    assert people["value"] is None and people["raw"] is None


def test_multiple_conditions_are_all_extracted():
    result = extract_entities("Two people trapped, one unconscious and bleeding")
    kinds = {c["type"] for c in result.conditions}
    assert {
        ConditionType.TRAPPED.value,
        ConditionType.UNCONSCIOUS.value,
        ConditionType.BLEEDING.value,
    } <= kinds


def test_resource_requests_and_hazards_are_extracted():
    result = extract_entities("Need ambulance, gas leak near the building")
    assert "AMBULANCE" in result.resources
    assert any("gas leak" in h for h in result.hazards)


def test_raw_spans_are_always_preserved():
    result = extract_entities("Three people trapped")
    assert all(span.raw for span in result.spans)


# ------------------------------------------------------------ transcription


def test_mock_transcription_per_language():
    for marker, language in (("EN", "en"), ("HI", "hi"), ("TA", "ta")):
        r = mocks.transcribe(marker.encode() + b"\x00" * 100, mime_type="audio/wav")
        assert r.language == language
        assert r.text and r.machine_generated and not r.low_quality


def test_transcription_preserves_the_original_audio_hash():
    audio = b"EN" + b"\x01" * 500
    import hashlib

    r = mocks.transcribe(audio, mime_type="audio/wav")
    assert r.audio_sha256 == hashlib.sha256(audio).hexdigest()


def test_unrecognized_audio_is_marked_low_quality_not_invented():
    r = mocks.transcribe(b"ZZ" + b"\x00" * 10, mime_type="audio/wav")
    assert r.low_quality and r.text == "" and r.confidence is None


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"mime_type": "application/x-sh"}, "unsupported_media_type"),
        ({"mime_type": "audio/wav", "duration_s": 10_000}, "audio_too_long"),
    ],
)
def test_transcription_input_validation(kwargs, code):
    with pytest.raises(AIError) as exc:
        mocks.transcribe(b"EN" + b"\x00" * 10, **kwargs)
    assert exc.value.code == code


def test_empty_audio_is_rejected():
    with pytest.raises(AIError) as exc:
        mocks.transcribe(b"", mime_type="audio/wav")
    assert exc.value.code == "empty_audio"


# --------------------------------------------------------------- embeddings


def test_paraphrases_are_more_similar_than_unrelated_reports():
    a = mocks.embed("Three people trapped under collapsed building")
    b = mocks.embed("Building collapsed, people are trapped inside")
    c = mocks.embed("Need blankets at the shelter tomorrow")
    assert mocks.cosine(a.vector, b.vector) > mocks.cosine(a.vector, c.vector)


def test_cross_language_reports_match():
    en = mocks.embed("Three people trapped under collapsed building")
    hi = mocks.embed("तीन लोग गिरी हुई इमारत में फंसे हैं")
    unrelated = mocks.embed("Need blankets at the shelter")
    assert mocks.cosine(en.vector, hi.vector) > mocks.cosine(en.vector, unrelated.vector)


def test_embeddings_are_deterministic_and_normalized():
    v = mocks.embed("fire").vector
    assert v == mocks.embed("fire").vector
    assert abs(sum(x * x for x in v) - 1.0) < 1e-9


# -------------------------------------------------------------- translation


@pytest.mark.parametrize("source,target", [("hi", "en"), ("ta", "en"), ("en", "ta")])
def test_supported_language_pairs_translate(source, target):
    text = {"hi": "तीन लोग फंसे", "ta": "மூன்று பேர் சிக்கி", "en": "three people trapped"}[source]
    r = mocks.translate(text, target_language=target)
    assert r.machine_generated and not r.human_verified
    assert r.source_language == source and r.target_language == target


def test_translation_preserves_numbers_and_coordinates():
    r = mocks.translate("तीन लोग फंसे 3 people at 12.97, 77.59", target_language="en")
    for token in ("3", "12.97", "77.59"):
        assert token in r.text
        assert token in r.preserved_tokens


def test_missing_translation_model_fails_structurally():
    with pytest.raises(AIError) as exc:
        mocks.translate("bonjour", source_language="fr", target_language="ta")
    assert exc.value.code == "unsupported_language_pair"


# ------------------------------------------------------------ summarization


def test_summary_sums_only_exact_counts_and_flags_the_rest():
    summary = mocks.summarize(
        [
            {"id": "i1", "people_affected": {"value": 3}, "original_text": "3 trapped"},
            {"id": "i2", "people_affected": {"value": 2}, "original_text": "2 trapped"},
            {
                "id": "i3",
                "people_affected": {"value": None, "raw": "several"},
                "original_text": "several trapped",
            },
        ]
    )
    assert summary.estimated_affected_people["value"] == 5
    assert summary.estimated_affected_people["reports_without_count"] == 1
    assert any("no exact count" in u for u in summary.uncertainties)
    assert set(summary.source_incident_ids) == {"i1", "i2", "i3"}


def test_summary_reports_conflicting_counts():
    summary = mocks.summarize(
        [{"id": "a", "people_affected": {"value": 3}}, {"id": "b", "people_affected": {"value": 9}}]
    )
    assert any("disagree" in u for u in summary.uncertainties)


def test_summary_never_invents_a_count_for_an_all_unknown_cluster():
    summary = mocks.summarize([{"id": "a", "people_affected": {"value": None}}])
    assert summary.estimated_affected_people["value"] is None


def test_summary_never_dispatches():
    summary = mocks.summarize([{"id": "a", "people_affected": {"value": 1}}])
    joined = " ".join(summary.recommended_human_actions).lower()
    assert "coordinator" in joined
    assert not any("dispatched" == a.lower() for a in summary.recommended_human_actions)


def test_empty_cluster_is_an_error_not_an_empty_summary():
    with pytest.raises(AIError) as exc:
        mocks.summarize([])
    assert exc.value.code == "empty_cluster"
