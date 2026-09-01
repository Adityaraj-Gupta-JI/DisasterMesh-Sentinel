"""Roles, permissions, and the tamper-evident audit ledger."""

from __future__ import annotations

from datetime import timedelta

import pytest
from dms.domain.enums import Permission, Role, Sensitivity
from dms.domain.errors import AuthorizationError
from dms.domain.models import NodeIdentity, SyncObject
from dms.governance.audit import EventLog
from dms.governance.authz import (
    can_read_plaintext,
    can_receive,
    has_permission,
    require_permission,
)


@pytest.mark.parametrize(
    "role,permission,expected",
    [
        (Role.CITIZEN_REPORTER, Permission.CREATE_INCIDENT, True),
        (Role.CITIZEN_REPORTER, Permission.ASSIGN_RESOURCE, False),
        (Role.CITIZEN_REPORTER, Permission.PUBLISH_ALERT, False),
        (Role.VOLUNTEER_RELAY, Permission.FORWARD_BUNDLE, True),
        (Role.VOLUNTEER_RELAY, Permission.VIEW_MEDICAL_DATA, False),
        (Role.EVENT_COORDINATOR, Permission.ASSIGN_RESOURCE, True),
        (Role.EVENT_COORDINATOR, Permission.PUBLISH_ALERT, False),
        (Role.MEDICAL_RESPONDER, Permission.VIEW_MEDICAL_DATA, True),
        (Role.GOVERNMENT_AUTHORITY, Permission.PUBLISH_ALERT, True),
        (Role.SYSTEM_ADMINISTRATOR, Permission.REVOKE_NODE, True),
    ],
)
def test_role_permission_matrix(role, permission, expected):
    assert has_permission(role, permission) is expected


def test_citizen_cannot_dispatch():
    with pytest.raises(AuthorizationError, match="ASSIGN_RESOURCE"):
        require_permission(Role.CITIZEN_REPORTER, Permission.ASSIGN_RESOURCE)


def test_only_authority_publishes_alerts():
    require_permission(Role.GOVERNMENT_AUTHORITY, Permission.PUBLISH_ALERT)
    for role in (Role.EVENT_COORDINATOR, Role.MEDICAL_RESPONDER, Role.CITIZEN_REPORTER):
        with pytest.raises(AuthorizationError):
            require_permission(role, Permission.PUBLISH_ALERT)


def test_relay_carries_but_never_reads_restricted_content(now):
    medical = SyncObject(
        bundle_id="b",
        sensitivity=Sensitivity.MEDICAL,
        allowed_roles=(Role.EVENT_COORDINATOR, Role.MEDICAL_RESPONDER, Role.VOLUNTEER_RELAY),
    )
    relay = NodeIdentity(id="B", role=Role.VOLUNTEER_RELAY)
    allowed, reason = can_receive(medical, relay, now=now)
    assert allowed is True and reason == "authorized"
    assert can_read_plaintext(Role.VOLUNTEER_RELAY, Sensitivity.MEDICAL) is False


def test_coordinator_and_medic_may_read_medical_content():
    for role in (Role.EVENT_COORDINATOR, Role.MEDICAL_RESPONDER):
        assert can_read_plaintext(role, Sensitivity.MEDICAL) is True


def test_revoked_node_receives_nothing(now):
    revoked = NodeIdentity(id="X", role=Role.EVENT_COORDINATOR, revoked=True)
    allowed, reason = can_receive(SyncObject(bundle_id="b"), revoked, now=now)
    assert allowed is False and reason == "receiver_revoked_or_expired"


def test_expired_credential_receives_nothing(now):
    expired = NodeIdentity(
        id="X", role=Role.MEDICAL_RESPONDER, credential_expires_at=now - timedelta(minutes=1)
    )
    allowed, _ = can_receive(SyncObject(bundle_id="b"), expired, now=now)
    assert allowed is False


# ------------------------------------------------------------- audit log


def test_ledger_chains_entries(clock):
    log = EventLog(clock)
    log.append("INCIDENT_CREATED", incident_id="i1")
    second = log.append("INCIDENT_ACKNOWLEDGED", incident_id="i1")
    assert second.prev_hash == log.entries[0].entry_hash
    assert log.verify() is True


def test_tampering_with_an_entry_is_detected(clock):
    log = EventLog(clock)
    log.append("A", incident_id="i1")
    log.append("B", incident_id="i1")
    log.entries[0].detail["injected"] = True
    assert log.verify() is False


def test_deleting_an_entry_is_detected(clock):
    log = EventLog(clock)
    for action in ("A", "B", "C"):
        log.append(action, incident_id="i1")
    assert log.verify(list(log.entries[:1] + log.entries[2:])) is False


def test_events_can_be_filtered_per_incident(clock):
    log = EventLog(clock)
    log.append("A", incident_id="i1")
    log.append("B", incident_id="i2")
    assert len(log.for_incident("i1")) == 1
