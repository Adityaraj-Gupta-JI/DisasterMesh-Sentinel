"""Inventory exchange and control-frame handling."""

from __future__ import annotations

import pytest
from dms.domain.enums import PayloadType, PriorityClass, Role, Sensitivity
from dms.domain.errors import ProtocolError
from dms.protocol.inventory import (
    BundleOffer,
    ControlMessage,
    ExactDigest,
    MessageType,
    missing_from,
)


def offer(bundle_id="b1", **kwargs) -> BundleOffer:
    base = dict(
        bundle_id=bundle_id,
        incident_id="i1",
        payload_type=PayloadType.INCIDENT_TEXT,
        priority_class=PriorityClass.P0,
        priority_score=90,
        size_bytes=100,
        sensitivity=Sensitivity.OPERATIONAL,
        expires_at="2026-01-01T01:00:00+00:00",
    )
    return BundleOffer(**(base | kwargs))


def test_digest_reports_membership():
    digest = ExactDigest(frozenset({"a", "b"}))
    assert digest.contains("a") and not digest.contains("z")


def test_only_missing_bundles_are_offered():
    theirs = ExactDigest(frozenset({"a", "b"}))
    assert missing_from(theirs, ["a", "b", "c", "d"]) == ["c", "d"]


def test_digest_round_trips():
    digest = ExactDigest(frozenset({"a", "b"}))
    assert ExactDigest.from_dict(digest.to_dict()).bundle_ids == digest.bundle_ids


def test_unknown_digest_kind_is_rejected():
    with pytest.raises(ProtocolError, match="unsupported digest kind"):
        ExactDigest.from_dict({"kind": "bloom", "bundle_ids": []})


def test_offer_carries_metadata_only():
    keys = set(offer().to_dict())
    assert "payload" not in keys and "original_text" not in keys
    assert {"bundle_id", "priority_class", "size_bytes", "sensitivity"} <= keys


def test_offer_round_trips():
    original = offer()
    assert BundleOffer.from_dict(original.to_dict()) == original


def test_malformed_offer_is_rejected():
    with pytest.raises(ProtocolError, match="malformed bundle offer"):
        BundleOffer.from_dict({"bundle_id": "b"})


def test_control_message_round_trips():
    msg = ControlMessage(
        type=MessageType.INVENTORY_REQUEST,
        node_id="A",
        role=Role.CITIZEN_REPORTER,
        body={"digest": ExactDigest(frozenset({"x"})).to_dict()},
    )
    decoded = ControlMessage.decode(msg.encode())
    assert decoded.type == msg.type and decoded.node_id == "A"
    assert decoded.role is Role.CITIZEN_REPORTER


def test_control_frames_are_distinguishable_from_bundle_frames():
    encoded = ControlMessage(type="X", node_id="A", role=Role.CITIZEN_REPORTER).encode()
    assert ControlMessage.is_control(encoded)
    assert not ControlMessage.is_control(b"BNDL....")


@pytest.mark.parametrize("frame", [b"", b"CTRL{", b"CTRLnull", b"CTRL[]", b"NOPE{}"])
def test_malformed_control_frames_raise_not_crash(frame):
    with pytest.raises(ProtocolError):
        ControlMessage.decode(frame)


def test_unsupported_inventory_version_is_rejected():
    import json

    bad = (
        b"CTRL"
        + json.dumps(
            {
                "type": "X",
                "node_id": "A",
                "role": "CITIZEN_REPORTER",
                "version": "inv/99",
                "body": {},
            }
        ).encode()
    )
    with pytest.raises(ProtocolError, match="unsupported inventory version"):
        ControlMessage.decode(bad)
