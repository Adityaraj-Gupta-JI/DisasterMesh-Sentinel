"""Duplicate detection: narrow first, then compare, and never merge silently."""

from __future__ import annotations

from datetime import timedelta

from dms.ai.clustering import candidates, cluster, compare, decide, split
from dms.domain.enums import ClusterDecision, DisasterType
from dms.domain.models import GeoPoint, Incident

MARKET = GeoPoint(latitude=12.9716, longitude=77.5946)
FAR = GeoPoint(latitude=13.4000, longitude=77.9000)


def report(text, when, location=MARKET, types=(DisasterType.BUILDING_COLLAPSE,)) -> Incident:
    return Incident(
        source_node_id="A",
        original_text=text,
        reported_at=when,
        location=location,
        disaster_types=types,
    )


def test_paraphrases_of_the_same_event_are_merged(now):
    a = report("Three people trapped under collapsed building", now)
    b = report("Building collapsed, people trapped inside", now + timedelta(minutes=3))
    assert decide(compare(a, b)) in (ClusterDecision.MERGE, ClusterDecision.LINK)


def test_cross_language_reports_of_one_event_are_associated(now):
    a = report("Three people trapped under collapsed building", now)
    b = report("तीन लोग गिरी हुई इमारत में फंसे हैं", now + timedelta(minutes=2))
    assert decide(compare(a, b)) is not ClusterDecision.KEEP_SEPARATE


def test_same_category_far_apart_stays_separate(now):
    a = report("Building collapsed with people trapped", now)
    b = report("Building collapsed with people trapped", now, location=FAR)
    assert compare(a, b).geographic == 0.0
    assert b not in candidates(a, [b]), "distance must exclude before similarity is computed"


def test_same_place_much_later_stays_separate(now):
    a = report("Building collapsed", now)
    b = report("Building collapsed", now + timedelta(hours=6))
    assert candidates(a, [b]) == []


def test_similar_words_different_events_are_not_merged(now):
    a = report("Fire in the market building", now, types=(DisasterType.FIRE,))
    b = report(
        "Need water at the shelter", now + timedelta(minutes=5), types=(DisasterType.LOGISTICS,)
    )
    assert decide(compare(a, b)) is ClusterDecision.KEEP_SEPARATE


def test_cluster_is_provisional_and_explains_itself(now):
    a = report("Three people trapped under collapsed building", now)
    b = report("Building collapsed, people trapped inside", now + timedelta(minutes=2))
    result = cluster(a, [b])
    assert result is not None
    assert result.provisional is True and result.human_reviewed is False
    assert len(result.rationale) == 4
    assert result.embedding_model_version


def test_no_candidates_produces_no_cluster(now):
    a = report("Building collapsed", now)
    assert cluster(a, []) is None


def test_human_split_keeps_both_reports(now):
    a = report("Three people trapped under collapsed building", now)
    b = report("Building collapsed, people trapped inside", now + timedelta(minutes=2))
    result = cluster(a, [b])
    after = split(result, b.id)
    assert b.id not in after.incident_ids
    assert after.human_reviewed is True and after.provisional is False
    assert any("human split" in r for r in after.rationale)
