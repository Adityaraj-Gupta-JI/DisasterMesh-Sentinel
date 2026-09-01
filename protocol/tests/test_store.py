"""Local persistence: migrations, indexes, idempotency, atomicity, recovery."""

from __future__ import annotations

from datetime import timedelta

import pytest
from dms.domain.enums import IncidentStatus, PayloadType, PriorityClass, Role
from dms.domain.models import Acknowledgement, Incident, NodeIdentity, SyncObject
from dms.governance.audit import EventLog
from dms.protocol.bundle import Bundle
from dms.store.sqlite import SqliteStore


@pytest.fixture
def store(tmp_path) -> SqliteStore:
    return SqliteStore(tmp_path / "node.db")


def incident(**kwargs) -> Incident:
    return Incident(**({"source_node_id": "A", "original_text": "Three trapped"} | kwargs))


def test_migrations_apply_and_are_idempotent(store):
    assert store.schema_version == 1
    assert store.migrate() == 1


def test_indexes_exist_for_the_hot_queries(store):
    rows = store._conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    names = {r["name"] for r in rows}
    assert {
        "idx_incidents_status",
        "idx_incidents_priority",
        "idx_incidents_expiry",
        "idx_bundles_expiry",
        "idx_sync_priority",
    } <= names


def test_incident_upsert_is_idempotent(store):
    inc = incident()
    store.upsert_incident(inc)
    store.upsert_incident(inc)
    assert store.count_incidents() == 1


def test_a_stale_revision_never_overwrites_a_newer_one(store, now):
    inc = incident()
    store.upsert_incident(inc)
    newer = store.get_incident(inc.id)
    newer.status = IncidentStatus.ACKNOWLEDGED
    newer.touch(now)
    store.upsert_incident(newer)
    store.upsert_incident(inc)  # the old revision arrives late over the mesh
    assert store.get_incident(inc.id).status is IncidentStatus.ACKNOWLEDGED


def test_duplicate_bundle_insertion_is_safe(store, now):
    bundle = Bundle.create(
        incident_id="i1",
        source_node_id="A",
        payload=b"x",
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
    )
    assert store.save_bundle(bundle) is True
    assert store.save_bundle(bundle) is False
    assert len(store.bundle_ids()) == 1


def test_expired_bundle_query(store, now):
    fresh = Bundle.create(
        incident_id="i",
        source_node_id="A",
        payload=b"a",
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
        ttl_seconds=3600,
    )
    stale = Bundle.create(
        incident_id="i",
        source_node_id="A",
        payload=b"b",
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
        ttl_seconds=1,
    )
    store.save_bundle(fresh)
    store.save_bundle(stale)
    expired = store.expired_bundles(now + timedelta(seconds=2))
    assert expired == [stale.id]


def test_highest_priority_pending_sync_objects_come_first(store, now):
    for bundle_id, cls, score in [
        ("c", PriorityClass.P2, 30),
        ("a", PriorityClass.P0, 95),
        ("b", PriorityClass.P1, 60),
    ]:
        store.upsert_sync_object(
            SyncObject(
                bundle_id=bundle_id, incident_id="i", priority_class=cls, priority_score=score
            )
        )
    assert [o.bundle_id for o in store.pending_sync_objects(now)] == ["a", "b", "c"]


def test_expired_sync_objects_are_filtered_out(store, now):
    store.upsert_sync_object(
        SyncObject(bundle_id="gone", incident_id="i", expires_at=now - timedelta(seconds=1))
    )
    assert store.pending_sync_objects(now) == []


def test_duplicate_acknowledgement_is_absorbed(store):
    first = Acknowledgement(incident_id="i1", node_id="C")
    again = Acknowledgement(incident_id="i1", node_id="C")
    assert store.save_acknowledgement(first) is True
    assert store.save_acknowledgement(again) is False
    assert len(store.acknowledgements_for("i1")) == 1


def test_lifecycle_change_and_audit_entry_commit_together(store, clock):
    inc = incident()
    store.upsert_incident(inc)
    log = EventLog(clock)
    inc.status = IncidentStatus.ACKNOWLEDGED
    inc.touch(clock.now())
    entry = log.append("INCIDENT_ACKNOWLEDGED", incident_id=inc.id)
    store.transition_with_event(inc, entry)

    assert store.get_incident(inc.id).status is IncidentStatus.ACKNOWLEDGED
    assert [e["action"] for e in store.events(inc.id)] == ["INCIDENT_ACKNOWLEDGED"]


def test_failed_transition_rolls_back_both_writes(store, clock, monkeypatch):
    inc = incident()
    store.upsert_incident(inc)
    log = EventLog(clock)
    inc.status = IncidentStatus.ACKNOWLEDGED
    entry = log.append("INCIDENT_ACKNOWLEDGED", incident_id=inc.id)
    entry.detail = {"unserializable": object()}  # json.dumps will fail mid-transaction

    with pytest.raises(TypeError):
        store.transition_with_event(inc, entry)
    assert store.get_incident(inc.id).status is IncidentStatus.DRAFT
    assert store.events(inc.id) == []


def test_data_survives_a_restart(tmp_path, now):
    path = tmp_path / "node.db"
    store = SqliteStore(path)
    inc = incident()
    store.upsert_incident(inc)
    store.save_acknowledgement(Acknowledgement(incident_id=inc.id, node_id="C"))
    store.close()

    reopened = SqliteStore(path)
    assert reopened.count_incidents() == 1
    assert reopened.get_incident(inc.id).original_text == "Three trapped"
    assert len(reopened.acknowledgements_for(inc.id)) == 1


def test_observers_are_notified_of_writes(store):
    seen = []
    unsubscribe = store.observe(seen.append)
    store.upsert_incident(incident())
    assert "incidents" in seen
    unsubscribe()
    store.upsert_incident(incident())
    assert seen.count("incidents") == 1


def test_a_failing_observer_does_not_break_a_write(store):
    store.observe(lambda table: (_ for _ in ()).throw(RuntimeError("bad observer")))
    store.upsert_incident(incident())
    assert store.count_incidents() == 1


def test_filtering_by_status_and_priority(store):
    store.upsert_incident(incident(priority_class=PriorityClass.P0, status=IncidentStatus.QUEUED))
    store.upsert_incident(incident(priority_class=PriorityClass.P3, status=IncidentStatus.RESOLVED))
    assert len(store.list_incidents(priority=PriorityClass.P0)) == 1
    assert len(store.list_incidents(status=IncidentStatus.RESOLVED)) == 1


def test_node_identity_round_trips(store, now):
    node = NodeIdentity(id="A", role=Role.VOLUNTEER_RELAY, organization_id="org")
    store.save_node(node)
    assert store.get_node("A").role is Role.VOLUNTEER_RELAY
