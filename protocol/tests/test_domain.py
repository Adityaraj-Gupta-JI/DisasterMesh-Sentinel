"""Domain model validation and lifecycle rules."""

from __future__ import annotations

from datetime import timedelta

import pytest
from dms.domain.enums import ConditionType, Role
from dms.domain.enums import IncidentStatus as S
from dms.domain.errors import AuthorizationError, LifecycleError, ValidationError
from dms.domain.lifecycle import can_transition, transition
from dms.domain.models import (
    Attachment,
    Condition,
    GeoPoint,
    Incident,
    NodeIdentity,
    Quantity,
)


def incident(**kwargs) -> Incident:
    base = dict(source_node_id="node_a", original_text="Three people trapped")
    return Incident(**(base | kwargs))


def test_incident_requires_a_source_node():
    with pytest.raises(ValidationError, match="source node"):
        Incident(source_node_id="", original_text="help")


def test_incident_requires_text_or_audio_reference():
    with pytest.raises(ValidationError):
        incident(original_text="   ")
    # An audio-only report is legitimate: the transcript may never arrive.
    assert incident(original_text="", audio_reference="file://a.wav").audio_reference


def test_priority_score_out_of_range_is_rejected():
    with pytest.raises(ValidationError, match="priority score"):
        incident(priority_score=101)


def test_severity_out_of_range_is_rejected():
    with pytest.raises(ValidationError, match="severity"):
        incident(severity=-1)


def test_unknown_people_count_is_explicit_not_zero():
    q = Quantity.unknown(raw="some people")
    assert q.is_unknown and q.value is None and q.approximate
    assert q.value != 0, "unknown must never be silently treated as zero"


def test_attachment_hash_must_be_a_sha256_digest():
    with pytest.raises(ValidationError, match="sha256"):
        Attachment(incident_id="i", sha256="abc")


def test_expired_incident_reports_expiry(now):
    inc = incident(expires_at=now + timedelta(seconds=10))
    assert not inc.is_expired(now)
    assert inc.is_expired(now + timedelta(seconds=11))


def test_geo_precision_can_be_coarsened_for_unauthorized_roles():
    precise = GeoPoint(latitude=12.971598, longitude=77.594566, accuracy_m=5)
    coarse = precise.coarse()
    assert coarse.shared_precisely is False
    assert coarse.latitude == 12.97 and coarse.accuracy_m >= 1000


def test_redaction_strips_medical_detail_but_keeps_the_record():
    inc = incident(
        conditions=(Condition(type=ConditionType.UNCONSCIOUS),),
        people_affected=Quantity(value=3, raw="Three"),
        location=GeoPoint(latitude=12.9716, longitude=77.5946),
    )
    safe = inc.redacted_for(precise_location=False, medical=False)
    assert safe.conditions == ()
    assert safe.people_affected.is_unknown
    assert safe.location.shared_precisely is False
    assert inc.conditions, "redaction must not mutate the original"


def test_touch_bumps_revision(now):
    inc = incident()
    before = inc.revision
    inc.touch(now)
    assert inc.revision == before + 1


@pytest.mark.parametrize(
    "current,target,allowed",
    [
        (S.DRAFT, S.QUEUED, True),
        (S.QUEUED, S.RELAYED, True),
        (S.RECEIVED, S.ACKNOWLEDGED, True),
        (S.ACKNOWLEDGED, S.DISPATCH_REQUESTED, True),
        (S.DISPATCHED, S.EN_ROUTE, True),
        (S.RESOLVED, S.QUEUED, False),
        (S.DRAFT, S.DISPATCHED, False),
        (S.CANCELLED, S.ACKNOWLEDGED, False),
        (S.QUEUED, S.ARRIVED, False),
    ],
)
def test_lifecycle_transition_matrix(current, target, allowed):
    assert can_transition(current, target) is allowed


def test_illegal_transition_raises(now):
    inc = incident(status=S.DRAFT)
    with pytest.raises(LifecycleError, match="illegal transition"):
        transition(inc, S.DISPATCHED, role=Role.EVENT_COORDINATOR, now=now)


def test_duplicate_transition_is_idempotent_not_an_error(now):
    inc = incident(status=S.RECEIVED)
    assert transition(inc, S.ACKNOWLEDGED, role=Role.EVENT_COORDINATOR, now=now) is True
    assert transition(inc, S.ACKNOWLEDGED, role=Role.EVENT_COORDINATOR, now=now) is False


def test_resolution_requires_an_authorized_role(now):
    inc = incident(status=S.ACKNOWLEDGED)
    with pytest.raises(AuthorizationError, match="CLOSE_INCIDENT"):
        transition(inc, S.RESOLVED, role=Role.CITIZEN_REPORTER, now=now)
    assert transition(inc, S.RESOLVED, role=Role.EVENT_COORDINATOR, now=now) is True


def test_expiry_does_not_erase_history(now):
    inc = incident(status=S.QUEUED)
    transition(inc, S.EXPIRED, role=Role.EVENT_COORDINATOR, now=now)
    assert inc.original_text == "Three people trapped"
    # An expired P0 can still be acknowledged — it does not vanish from the inbox.
    assert can_transition(S.EXPIRED, S.ACKNOWLEDGED)


def test_node_credentials_can_expire_and_be_revoked(now):
    node = NodeIdentity(credential_expires_at=now + timedelta(hours=1))
    assert node.is_active(now)
    assert not node.is_active(now + timedelta(hours=2))
    node.revoked = True
    assert not node.is_active(now)
