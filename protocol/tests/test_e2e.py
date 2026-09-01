"""End-to-end: the ten MVP acceptance criteria, offline, over a mock mesh.

Reporter A → Relay B → Coordinator C. No internet, no radios, no real models.
"""

from __future__ import annotations

import json

import pytest
from dms.dispatch.service import DispatchService, default_resources
from dms.domain.enums import (
    AttachmentKind,
    DispatchStatus,
    IncidentStatus,
    PayloadType,
    PriorityClass,
    Role,
)

IMAGE = b"\xff\xd8\xff" + b"collapse-photo" * 8_000
REPORT = "Three people trapped under collapsed building near Market Road"


@pytest.fixture
def abc(mesh):
    """A reported P0 incident, relayed A→B→C, ready to inspect."""
    a, b, c = mesh.nodes["A"], mesh.nodes["B"], mesh.nodes["C"]
    incident = a.report_incident(REPORT)
    a.attach(
        incident.id,
        IMAGE,
        file_name="collapse.jpg",
        mime_type="image/jpeg",
        kind=AttachmentKind.IMAGE,
    )
    mesh.connect("A", "B")
    mesh.exchange("A", "B")
    mesh.connect("B", "C")
    mesh.exchange("B", "C")
    return mesh, a, b, c, incident


# ------------------------------------------------- the ten MVP criteria


def test_1_reporter_creates_a_text_incident(mesh):
    a = mesh.nodes["A"]
    incident = a.report_incident(REPORT)
    assert incident.original_text == REPORT
    assert a.store.get_incident(incident.id) is not None


def test_2_incident_receives_a_priority(mesh):
    incident = mesh.nodes["A"].report_incident(REPORT)
    assert incident.priority_class is PriorityClass.P0
    assert incident.priority_score >= 85
    assert incident.priority_explanation, "the score must arrive with its reasoning"


def test_3_incident_is_encrypted_and_stored_locally(mesh):
    a = mesh.nodes["A"]
    incident = a.report_incident(REPORT)
    bundle = a.store.get_bundle(a.store.bundle_ids()[0])
    assert bundle.header.encryption["alg"] == "AES-256-GCM"
    assert b"trapped" not in bundle.payload, "plaintext must not sit on disk in a bundle"
    assert a.store.get_incident(incident.id).original_text == REPORT


def test_4_and_5_relay_receives_and_forwards_to_coordinator(abc):
    _mesh, a, b, c, incident = abc
    assert b.store.has_bundle(a.store.bundle_ids()[0])
    assert c.store.count_incidents() == 1
    assert b.sync.stats.bundles_sent > 0


def test_6_coordinator_sees_the_incident_with_original_text(abc):
    _mesh, _a, _b, c, incident = abc
    seen = c.store.get_incident(incident.id)
    assert seen is not None
    assert seen.original_text == REPORT, "original user input must survive every hop"
    assert seen.priority_class is PriorityClass.P0


def test_7_image_follows_the_text_and_is_verified(abc):
    _mesh, _a, _b, c, incident = abc
    attachments = c.store.attachments_for(incident.id)
    assert len(attachments) == 1
    committed = attachments[0]
    assert committed["committed"] is True
    from pathlib import Path

    assert Path(committed["local_path"]).read_bytes() == IMAGE


def test_8_coordinator_acknowledges(abc):
    _mesh, _a, _b, c, incident = abc
    c.acknowledge(incident.id, note="ambulance requested")
    assert c.store.get_incident(incident.id).status is IncidentStatus.ACKNOWLEDGED
    assert len(c.store.acknowledgements_for(incident.id)) == 1


def test_9_simulated_dispatch_can_be_created(abc):
    _mesh, _a, _b, c, incident = abc
    c.acknowledge(incident.id)
    service = DispatchService(c.store, c.event_log, c.clock)
    for resource in default_resources():
        service.register_resource(resource)

    seen = c.store.get_incident(incident.id)
    recommendations = service.recommend(seen)
    assert recommendations, "a collapse with trapped people must recommend something"
    assert all(r.reason for r in recommendations)

    order = service.create_order(
        seen, recommendations[0].resource.id, reason=recommendations[0].reason
    )
    assert order.status is DispatchStatus.RECOMMENDED, "creating must not dispatch"

    authorized = service.authorize(
        order, seen, actor_node_id=c.identity.id, actor_role=Role.EVENT_COORDINATOR
    )
    assert authorized.status is DispatchStatus.ASSIGNED
    assert authorized.simulated is True
    assert authorized.authorized_by_node_id == c.identity.id


def test_10_the_whole_flow_ran_with_no_internet(abc):
    _mesh, a, b, c, _incident = abc
    assert not any(n.config.online for n in (a, b, c))


# --------------------------------------------- ordering and idempotency


def test_text_arrives_before_the_image(abc):
    """The product's central promise: media never overtakes critical text."""
    _mesh, _a, _b, c, incident = abc
    received = [e for e in c.store.events(incident.id) if e["action"] == "BUNDLE_RECEIVED"]
    kinds = []
    for event in received:
        bundle = c.store.get_bundle(event["detail"]["bundle_id"])
        kinds.append(bundle.header.payload_type)
    text_at = kinds.index(PayloadType.INCIDENT_TEXT)
    chunk_at = kinds.index(PayloadType.ATTACHMENT_CHUNK)
    assert text_at < chunk_at, f"text must precede media, got {kinds}"


def test_path_is_a_to_b_to_c(abc):
    _mesh, a, _b, c, incident = abc
    text_bundle = next(
        c.store.get_bundle(bid)
        for bid in c.store.bundle_ids()
        if c.store.get_bundle(bid).header.payload_type is PayloadType.INCIDENT_TEXT
    )
    assert text_bundle.header.path == ("A", "B", "C")
    assert text_bundle.header.hop_count == 2


def test_duplicate_transfer_is_idempotent(abc):
    """Re-running the exchange must not duplicate incidents or bundles."""
    mesh, _a, _b, c, _incident = abc
    before = (c.store.count_incidents(), len(c.store.bundle_ids()))
    mesh.exchange("B", "C")
    mesh.exchange("B", "C")
    assert (c.store.count_incidents(), len(c.store.bundle_ids())) == before


def test_repeated_acknowledgement_is_absorbed(abc):
    _mesh, _a, _b, c, incident = abc
    first = c.acknowledge(incident.id)
    second = c.acknowledge(incident.id)
    assert len(c.store.acknowledgements_for(incident.id)) == 1
    assert first.dedup_key == second.dedup_key


def test_acknowledgement_propagates_back_to_the_reporter(abc):
    mesh, a, _b, c, incident = abc
    c.acknowledge(incident.id, note="on our way")
    mesh.exchange("C", "B")
    mesh.exchange("B", "A")
    assert a.store.get_incident(incident.id).status is IncidentStatus.ACKNOWLEDGED


# ------------------------------------------------------------- security


def test_relay_carries_ciphertext_it_cannot_read(abc):
    """A volunteer's phone stores encrypted evidence without being able to open it."""
    _mesh, _a, b, _c, incident = abc
    assert b.can_decrypt is False
    assert len(b.store.bundle_ids()) > 0
    assert b.store.get_incident(incident.id) is None, "relay must not reconstruct content"
    for bundle_id in b.store.bundle_ids():
        assert b"trapped" not in b.store.get_bundle(bundle_id).payload


def test_relay_status_exposes_counts_but_no_content(abc):
    _mesh, _a, b, _c, _incident = abc
    status = b.status()
    assert status["stored_bundles"] > 0 and status["can_read_payloads"] is False
    assert "trapped" not in json.dumps(status).lower()


def test_audit_chain_is_intact_and_covers_the_flow(abc):
    _mesh, _a, _b, c, incident = abc
    c.acknowledge(incident.id)
    assert c.event_log.verify() is True
    actions = {e["action"] for e in c.store.events(incident.id)}
    assert {"BUNDLE_RECEIVED", "ATTACHMENT_COMMITTED", "INCIDENT_ACKNOWLEDGED"} <= actions


def test_expired_bundles_are_not_forwarded(mesh, tmp_path):
    a, b = mesh.nodes["A"], mesh.nodes["B"]
    a.report_incident("Need water at the shelter")  # long TTL, low priority
    mesh.clock.advance(seconds=60 * 60 * 49)  # past even the P3 TTL
    mesh.connect("A", "B")
    mesh.exchange("A", "B")
    assert not b.store.has_bundle(a.store.bundle_ids()[0])


def test_node_survives_a_restart_with_its_data(abc, tmp_path):
    _mesh, _a, _b, c, incident = abc
    c.acknowledge(incident.id)
    path = c.store.path
    c.store.close()

    from dms.store.sqlite import SqliteStore

    reopened = SqliteStore(path)
    assert reopened.get_incident(incident.id).status is IncidentStatus.ACKNOWLEDGED
    assert len(reopened.acknowledgements_for(incident.id)) == 1
    assert reopened.attachments_for(incident.id)


# ------------------------------------------------------- degraded modes


def test_incident_reporting_works_with_ai_unavailable(mesh):
    a = mesh.nodes["A"]
    a.config.ai_available = False
    incident = a.report_incident(REPORT)
    assert incident.priority_class is PriorityClass.P0, "rules must still escalate"
    assert incident.original_text == REPORT
    assert any("AI unavailable" in e for e in incident.priority_explanation)


def test_a_paused_relay_does_not_forward(mesh):
    a, b, c = mesh.nodes["A"], mesh.nodes["B"], mesh.nodes["C"]
    a.report_incident(REPORT)
    mesh.connect("A", "B")
    mesh.exchange("A", "B")
    b.config.relay_enabled = False
    mesh.connect("B", "C")
    b.sync_with("C")
    mesh.radio.drain()
    assert c.store.count_incidents() == 0


def test_low_battery_relay_still_moves_p0_text(mesh):
    a, b, c = mesh.nodes["A"], mesh.nodes["B"], mesh.nodes["C"]
    incident = a.report_incident(REPORT)
    a.attach(incident.id, IMAGE, file_name="c.jpg", mime_type="image/jpeg")
    mesh.connect("A", "B")
    mesh.exchange("A", "B")
    b.config.battery = 0.05
    mesh.connect("B", "C")
    mesh.exchange("B", "C")
    assert c.store.get_incident(incident.id) is not None, "P0 text must survive low battery"
