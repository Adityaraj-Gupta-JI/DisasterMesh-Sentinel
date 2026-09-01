"""Duplicate detection and clustering.

Candidates are narrowed by time and geography before any similarity is computed, and
a merge is never automatic: high similarity produces a provisional cluster that a
human confirms, links, or splits. Source incidents are never deleted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta

from ..domain.clock import utc
from ..domain.enums import ClusterDecision
from ..domain.models import Incident, IncidentCluster
from . import mocks

TIME_WINDOW = timedelta(hours=2)
DISTANCE_LIMIT_KM = 2.0

MERGE_THRESHOLD = 0.80
LINK_THRESHOLD = 0.60
REVIEW_THRESHOLD = 0.45


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class SimilarityBreakdown:
    """Why two reports were judged alike — each signal separately visible."""

    semantic: float
    temporal: float
    geographic: float
    categorical: float
    combined: float
    rationale: tuple[str, ...]


def compare(a: Incident, b: Incident) -> SimilarityBreakdown:
    semantic = mocks.cosine(
        mocks.embed(a.original_text).vector, mocks.embed(b.original_text).vector
    )
    gap = abs((utc(a.reported_at) - utc(b.reported_at)).total_seconds())
    temporal = max(0.0, 1.0 - gap / TIME_WINDOW.total_seconds())

    if a.location and b.location:
        km = haversine_km(
            a.location.latitude, a.location.longitude, b.location.latitude, b.location.longitude
        )
        geographic = max(0.0, 1.0 - km / DISTANCE_LIMIT_KM)
        geo_note = f"{km:.2f} km apart"
    else:
        geographic = 0.5
        geo_note = "location missing on at least one report"

    shared = set(a.disaster_types) & set(b.disaster_types)
    union = set(a.disaster_types) | set(b.disaster_types)
    categorical = len(shared) / len(union) if union else 0.0

    # Content decides whether two reports describe one event; proximity only
    # sharpens or softens that judgement. During a disaster every report is close
    # in time and space, so proximity alone must never associate two incidents.
    content = 0.60 * semantic + 0.40 * categorical
    proximity = 0.50 + 0.25 * temporal + 0.25 * geographic
    combined = content * proximity
    return SimilarityBreakdown(
        semantic=semantic,
        temporal=temporal,
        geographic=geographic,
        categorical=categorical,
        combined=combined,
        rationale=(
            f"semantic {semantic:.2f}",
            f"temporal {temporal:.2f} ({gap / 60:.0f} min apart)",
            f"geographic {geographic:.2f} ({geo_note})",
            f"categorical {categorical:.2f} (shared: {', '.join(sorted(t.value for t in shared)) or 'none'})",
        ),
    )


def decide(breakdown: SimilarityBreakdown) -> ClusterDecision:
    if breakdown.combined >= MERGE_THRESHOLD:
        return ClusterDecision.MERGE
    if breakdown.combined >= LINK_THRESHOLD:
        return ClusterDecision.LINK
    if breakdown.combined >= REVIEW_THRESHOLD:
        return ClusterDecision.REVIEW_REQUIRED
    return ClusterDecision.KEEP_SEPARATE


def candidates(incident: Incident, pool: list[Incident]) -> list[Incident]:
    """Narrow by time and geography before spending effort on similarity."""
    out = []
    for other in pool:
        if other.id == incident.id:
            continue
        if abs((utc(other.reported_at) - utc(incident.reported_at)).total_seconds()) > (
            TIME_WINDOW.total_seconds()
        ):
            continue
        if incident.location and other.location:
            km = haversine_km(
                incident.location.latitude,
                incident.location.longitude,
                other.location.latitude,
                other.location.longitude,
            )
            if km > DISTANCE_LIMIT_KM * 2:
                continue
        out.append(other)
    return out


def cluster(incident: Incident, pool: list[Incident]) -> IncidentCluster | None:
    """Build a provisional cluster for ``incident``. Always human-reviewable."""
    matches: list[tuple[Incident, SimilarityBreakdown]] = []
    for other in candidates(incident, pool):
        breakdown = compare(incident, other)
        if decide(breakdown) in (
            ClusterDecision.MERGE,
            ClusterDecision.LINK,
            ClusterDecision.REVIEW_REQUIRED,
        ):
            matches.append((other, breakdown))
    if not matches:
        return None
    best = max(matches, key=lambda m: m[1].combined)
    return IncidentCluster(
        incident_ids=tuple([incident.id] + [m[0].id for m in matches]),
        decision=decide(best[1]),
        similarity=round(best[1].combined, 4),
        embedding_model_version=mocks.EMBED_MOCK.version,
        provisional=True,
        human_reviewed=False,
        rationale=best[1].rationale,
        created_at=incident.reported_at,
    )


def split(cluster_obj: IncidentCluster, incident_id: str) -> IncidentCluster:
    """A human pulls one report out. Nothing is deleted; the cluster is marked reviewed."""
    remaining = tuple(i for i in cluster_obj.incident_ids if i != incident_id)
    return IncidentCluster(
        id=cluster_obj.id,
        incident_ids=remaining,
        decision=ClusterDecision.KEEP_SEPARATE if len(remaining) < 2 else cluster_obj.decision,
        similarity=cluster_obj.similarity,
        embedding_model_version=cluster_obj.embedding_model_version,
        provisional=False,
        human_reviewed=True,
        rationale=cluster_obj.rationale + (f"human split out {incident_id}",),
        created_at=cluster_obj.created_at,
    )
