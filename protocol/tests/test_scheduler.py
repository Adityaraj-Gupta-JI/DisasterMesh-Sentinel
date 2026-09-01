"""Emergency Sync Engine scheduling guarantees."""

from __future__ import annotations

from datetime import timedelta

import pytest
from dms.domain.enums import PayloadType, PriorityClass, Role, Sensitivity
from dms.domain.models import NodeIdentity, SyncObject
from dms.priority.policies import SyncContext
from dms.sync.scheduler import SyncScheduler


def obj(bundle_id: str, **kwargs) -> SyncObject:
    base = dict(
        bundle_id=bundle_id,
        incident_id="inc_1",
        payload_type=PayloadType.INCIDENT_TEXT,
        priority_class=PriorityClass.P2,
        priority_score=50,
        size_bytes=500,
    )
    return SyncObject(**(base | kwargs))


@pytest.fixture
def coordinator() -> NodeIdentity:
    return NodeIdentity(id="C", role=Role.EVENT_COORDINATOR)


@pytest.fixture
def scheduler() -> SyncScheduler:
    return SyncScheduler()


def selected_ids(result) -> list[str]:
    return [o.bundle_id for o in result.selected]


def test_p0_text_beats_p0_image(scheduler, coordinator, now):
    result = scheduler.select(
        [
            obj(
                "image",
                payload_type=PayloadType.ATTACHMENT_CHUNK,
                priority_class=PriorityClass.P0,
                priority_score=95,
                size_bytes=200_000,
            ),
            obj("text", priority_class=PriorityClass.P0, priority_score=90),
        ],
        receiver=coordinator,
        now=now,
    )
    assert selected_ids(result)[0] == "text"


def test_priority_classes_are_ordered(scheduler, coordinator, now):
    result = scheduler.select(
        [
            obj("p3", priority_class=PriorityClass.P3, priority_score=5),
            obj("p1", priority_class=PriorityClass.P1, priority_score=65),
            obj("p0", priority_class=PriorityClass.P0, priority_score=90),
            obj("p2", priority_class=PriorityClass.P2, priority_score=40),
        ],
        receiver=coordinator,
        now=now,
    )
    assert selected_ids(result) == ["p0", "p1", "p2", "p3"]


def test_expired_objects_are_never_scheduled(scheduler, coordinator, now):
    result = scheduler.select(
        [obj("gone", expires_at=now - timedelta(seconds=1), priority_class=PriorityClass.P0)],
        receiver=coordinator,
        now=now,
    )
    assert result.selected == []
    assert result.reasons_for(result.decisions[0].object_id) == ["expired"]


def test_restricted_object_is_not_offered_to_unauthorized_role(scheduler, now):
    medical = obj(
        "med",
        sensitivity=Sensitivity.MEDICAL,
        allowed_roles=(Role.EVENT_COORDINATOR, Role.MEDICAL_RESPONDER),
    )
    citizen = NodeIdentity(id="X", role=Role.CITIZEN_REPORTER)
    result = scheduler.select([medical], receiver=citizen, now=now)
    assert result.selected == []
    assert "role_not_in_allowed_roles" in result.reasons_for(medical.id)


def test_revoked_receiver_gets_nothing(scheduler, now):
    revoked = NodeIdentity(id="R", role=Role.EVENT_COORDINATOR, revoked=True)
    result = scheduler.select([obj("b")], receiver=revoked, now=now)
    assert result.selected == []
    assert "receiver_revoked_or_expired" in result.reasons_for(result.decisions[0].object_id)


def test_completed_object_is_not_retransmitted_as_new(scheduler, coordinator, now):
    already = obj("done", delivered_to=("C",))
    result = scheduler.select([already], receiver=coordinator, now=now)
    assert result.selected == []
    assert "already_delivered_to_receiver" in result.reasons_for(already.id)


def test_large_p3_file_does_not_starve_p0_text(scheduler, coordinator, now):
    result = scheduler.select(
        [
            obj(
                "huge_p3",
                payload_type=PayloadType.ATTACHMENT_CHUNK,
                priority_class=PriorityClass.P3,
                size_bytes=50_000_000,
            ),
            obj("p0_text", priority_class=PriorityClass.P0, priority_score=95),
        ],
        receiver=coordinator,
        now=now,
        max_bytes=1000,
    )
    assert selected_ids(result) == ["p0_text"]
    assert "byte_budget_exhausted" in result.reasons_for(
        next(d.object_id for d in result.decisions if d.bundle_id == "huge_p3")
    )


def test_media_defers_behind_a_pending_p0_text(scheduler, coordinator, now):
    result = scheduler.select(
        [
            obj(
                "p1_image",
                payload_type=PayloadType.ATTACHMENT_CHUNK,
                priority_class=PriorityClass.P1,
                size_bytes=100_000,
            ),
            obj("p0_text", priority_class=PriorityClass.P0, priority_score=95),
        ],
        receiver=coordinator,
        now=now,
    )
    assert selected_ids(result)[0] == "p0_text"


def test_low_battery_defers_non_critical_traffic(scheduler, coordinator, now):
    result = scheduler.select(
        [obj("p0", priority_class=PriorityClass.P0), obj("p2", priority_class=PriorityClass.P2)],
        receiver=coordinator,
        now=now,
        context=SyncContext(battery=0.12),
    )
    assert selected_ids(result) == ["p0"]


def test_every_decision_is_observable_and_explained(scheduler, coordinator, now):
    items = [obj("a"), obj("b", expires_at=now - timedelta(seconds=1))]
    result = scheduler.select(items, receiver=coordinator, now=now)
    assert len(result.decisions) == 2
    for decision in result.decisions:
        assert decision.reason
        assert decision.policy_version
        assert decision.receiver_role is Role.EVENT_COORDINATOR
        assert decision.timestamp == now
        assert decision.to_dict()["object_id"]


def test_expiry_urgency_promotes_soon_to_expire_objects(scheduler, coordinator, now):
    soon = obj("soon", priority_score=50, expires_at=now + timedelta(minutes=5))
    later = obj("later", priority_score=50, expires_at=now + timedelta(hours=10))
    result = scheduler.select([later, soon], receiver=coordinator, now=now)
    assert selected_ids(result)[0] == "soon"
