"""DMBP conformance: the eight protocol invariants, each with a test."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest
from dms.domain.enums import PayloadType, PriorityClass
from dms.domain.errors import ProtocolError
from dms.protocol.bundle import Bundle, BundleHeader, canonical_json, sha256_hex


def make(now, payload=b"three trapped", **kwargs) -> Bundle:
    return Bundle.create(
        incident_id="inc_1",
        source_node_id="node_a",
        payload=payload,
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
        **kwargs,
    )


def test_round_trip_serialization_preserves_every_field(now):
    original = make(now, priority_class=PriorityClass.P0, priority_score=91)
    restored = Bundle.from_wire(original.to_wire())
    assert restored.header.to_dict() == original.header.to_dict()
    assert restored.payload == original.payload


def test_canonical_serialization_is_byte_stable():
    a = canonical_json({"b": 1, "a": [3, 2]})
    b = canonical_json({"a": [3, 2], "b": 1})
    assert a == b, "key order must not change the bytes a signature covers"


def test_corrupted_payload_is_rejected(now):
    bundle = make(now)
    tampered = Bundle(header=bundle.header, payload=b"x" * len(bundle.payload))
    with pytest.raises(ProtocolError, match="hash mismatch"):
        tampered.verify_payload()


def test_expired_bundle_is_never_forwarded(now):
    bundle = make(now, ttl_seconds=60)
    later = now + timedelta(seconds=61)
    assert bundle.is_expired(later)
    assert bundle.can_forward(later) == (False, "expired")
    with pytest.raises(ProtocolError):
        bundle.forwarded("node_b", later)


def test_hop_limit_is_enforced_and_hop_count_never_decreases(now):
    bundle = make(now, hop_limit=2)
    first = bundle.forwarded("b", now)
    second = first.forwarded("c", now)
    assert (first.header.hop_count, second.header.hop_count) == (1, 2)
    assert second.can_forward(now) == (False, "hop_limit_reached")
    with pytest.raises(ProtocolError):
        second.forwarded("d", now)


def test_replication_limit_is_enforced(now):
    bundle = make(now, replication_limit=1, hop_limit=10)
    once = bundle.forwarded("b", now)
    assert once.can_forward(now) == (False, "replication_limit_reached")


def test_bundle_id_and_payload_hash_are_immutable(now):
    bundle = make(now)
    with pytest.raises(dataclasses.FrozenInstanceError):
        bundle.header.bundle_id = "other"  # the header is a frozen dataclass
    forwarded = bundle.forwarded("b", now)
    assert forwarded.header.bundle_id == bundle.header.bundle_id
    assert forwarded.header.payload_hash == bundle.header.payload_hash


def test_path_records_the_route_the_bundle_travelled(now):
    """The path reads as a route: originator, then each node that received it."""
    bundle = make(now)
    relayed = bundle.forwarded("B", now).forwarded("C", now)
    assert relayed.header.path == ("node_a", "B", "C")


def test_unknown_protocol_version_fails_closed(now):
    d = make(now).header.to_dict()
    d["protocol_version"] = "dmbp/999"
    with pytest.raises(ProtocolError, match="unsupported protocol version"):
        BundleHeader.from_dict(d)


def test_critical_text_is_independent_of_attachments(now):
    text = make(now, priority_class=PriorityClass.P0)
    image = Bundle.create(
        incident_id="inc_1",
        source_node_id="node_a",
        payload=b"\xff\xd8" * 100,
        payload_type=PayloadType.ATTACHMENT_CHUNK,
        now=now,
        priority_class=PriorityClass.P0,
    )
    assert text.id != image.id
    assert text.header.incident_id == image.header.incident_id
    # Losing the image bundle entirely leaves the text bundle fully valid.
    text.validate(now)


@pytest.mark.parametrize(
    "frame",
    [
        b"",
        b"ab",
        (0).to_bytes(4, "big"),
        (999999).to_bytes(4, "big") + b"{}",
        (2).to_bytes(4, "big") + b"xx",
        (4).to_bytes(4, "big") + b"null",
    ],
)
def test_malformed_frames_raise_protocol_error_not_crash(frame):
    with pytest.raises(ProtocolError):
        Bundle.from_wire(frame)


def test_size_mismatch_is_rejected(now):
    bundle = make(now)
    lying = Bundle(header=bundle.header, payload=bundle.payload + b"extra")
    with pytest.raises(ProtocolError, match="size mismatch"):
        lying.verify_payload()


def test_payload_hash_matches_sha256_of_payload(now):
    bundle = make(now)
    assert bundle.header.payload_hash == sha256_hex(bundle.payload)
