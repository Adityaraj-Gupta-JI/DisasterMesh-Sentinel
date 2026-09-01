"""Property and fuzz tests.

The bar: malformed input is rejected with a domain error and never crashes the
process, never commits a file, and never silently corrupts state.
"""

from __future__ import annotations

import random
import string
from datetime import timedelta

import pytest
from dms.domain.enums import PayloadType, PriorityClass, Role
from dms.domain.errors import ProtocolError, TransferError
from dms.domain.models import NodeIdentity, SyncObject
from dms.files.manifest import FileManifest
from dms.protocol.bundle import Bundle, BundleHeader
from dms.protocol.inventory import BundleOffer, ControlMessage
from dms.sync.scheduler import SyncScheduler

SEED = 20260831
random.seed(SEED)


def random_bytes(rng: random.Random, n: int = 64) -> bytes:
    return bytes(rng.getrandbits(8) for _ in range(n))


def random_json_like(rng: random.Random):
    kind = rng.choice(["int", "str", "list", "dict", "none", "float", "bool"])
    if kind == "int":
        return rng.randint(-(2**40), 2**40)
    if kind == "float":
        return rng.uniform(-1e9, 1e9)
    if kind == "str":
        return "".join(rng.choice(string.printable) for _ in range(rng.randint(0, 40)))
    if kind == "list":
        return [rng.randint(0, 100) for _ in range(rng.randint(0, 5))]
    if kind == "dict":
        return {"k": rng.randint(0, 10)}
    if kind == "bool":
        return rng.choice([True, False])
    return None


# ----------------------------------------------------------------- properties


def test_property_bundle_round_trip_preserves_valid_data(now):
    rng = random.Random(SEED)
    for _ in range(200):
        payload = random_bytes(rng, rng.randint(0, 512))
        bundle = Bundle.create(
            incident_id=f"inc_{rng.randint(0, 999)}",
            source_node_id="node_a",
            payload=payload,
            payload_type=rng.choice(list(PayloadType)),
            now=now,
            ttl_seconds=rng.randint(1, 10_000),
            priority_class=rng.choice(list(PriorityClass)),
            priority_score=rng.randint(0, 100),
        )
        restored = Bundle.from_wire(bundle.to_wire())
        assert restored.payload == payload
        assert restored.header.to_dict() == bundle.header.to_dict()
        restored.verify_payload()


def test_property_hop_count_never_decreases(now):
    rng = random.Random(SEED + 1)
    for _ in range(100):
        bundle = Bundle.create(
            incident_id="i",
            source_node_id="a",
            payload=b"x",
            payload_type=PayloadType.INCIDENT_TEXT,
            now=now,
            hop_limit=rng.randint(1, 8),
            replication_limit=99,
        )
        previous = bundle.header.hop_count
        while bundle.can_forward(now)[0]:
            bundle = bundle.forwarded(f"n{previous}", now)
            assert bundle.header.hop_count > previous
            previous = bundle.header.hop_count


def test_property_expired_objects_are_never_scheduled(now):
    rng = random.Random(SEED + 2)
    scheduler = SyncScheduler()
    receiver = NodeIdentity(id="C", role=Role.EVENT_COORDINATOR)
    for _ in range(100):
        objects = [
            SyncObject(
                bundle_id=f"b{i}",
                incident_id="i",
                priority_class=rng.choice(list(PriorityClass)),
                priority_score=rng.randint(0, 100),
                size_bytes=rng.randint(0, 10_000),
                expires_at=now + timedelta(seconds=rng.randint(-1000, 1000)),
            )
            for i in range(8)
        ]
        result = scheduler.select(objects, receiver=receiver, now=now)
        assert all(not o.is_expired(now) for o in result.selected)


def test_property_p0_text_is_always_schedulable_under_media_load(now):
    rng = random.Random(SEED + 3)
    scheduler = SyncScheduler()
    receiver = NodeIdentity(id="C", role=Role.EVENT_COORDINATOR)
    for _ in range(100):
        media = [
            SyncObject(
                bundle_id=f"m{i}",
                incident_id="i",
                payload_type=PayloadType.ATTACHMENT_CHUNK,
                priority_class=rng.choice(list(PriorityClass)),
                priority_score=rng.randint(0, 100),
                size_bytes=rng.randint(10**5, 10**7),
            )
            for i in range(rng.randint(1, 20))
        ]
        text = SyncObject(
            bundle_id="p0text",
            incident_id="i",
            payload_type=PayloadType.INCIDENT_TEXT,
            priority_class=PriorityClass.P0,
            priority_score=95,
            size_bytes=400,
        )
        rng.shuffle(media)
        result = scheduler.select(media + [text], receiver=receiver, now=now, max_bytes=1000)
        assert result.selected[0].bundle_id == "p0text"


def test_property_duplicate_application_is_idempotent(mesh):
    a, b = mesh.nodes["A"], mesh.nodes["B"]
    a.report_incident("Three people trapped under collapsed building")
    mesh.connect("A", "B")
    for _ in range(5):
        mesh.exchange("A", "B")
    assert len(b.store.bundle_ids()) == len(a.store.bundle_ids())
    assert b.sync.stats.bundles_received == len(a.store.bundle_ids())


def test_property_scheduler_output_is_a_subset_of_its_input(now):
    rng = random.Random(SEED + 4)
    scheduler = SyncScheduler()
    for _ in range(50):
        objects = [
            SyncObject(
                bundle_id=f"b{i}", incident_id="i", priority_class=rng.choice(list(PriorityClass))
            )
            for i in range(rng.randint(0, 10))
        ]
        receiver = NodeIdentity(id="C", role=rng.choice(list(Role)))
        result = scheduler.select(objects, receiver=receiver, now=now)
        assert {o.bundle_id for o in result.selected} <= {o.bundle_id for o in objects}
        assert len(result.decisions) == len(objects), "every object gets a verdict"


# ---------------------------------------------------------------------- fuzz


def test_fuzz_random_bytes_never_crash_bundle_parsing():
    rng = random.Random(SEED + 5)
    for _ in range(500):
        data = random_bytes(rng, rng.randint(0, 200))
        try:
            Bundle.from_wire(data)
        except ProtocolError:
            pass  # the only acceptable failure


def test_fuzz_random_bytes_never_crash_control_parsing():
    rng = random.Random(SEED + 6)
    for _ in range(500):
        data = b"CTRL" + random_bytes(rng, rng.randint(0, 100))
        try:
            ControlMessage.decode(data)
        except ProtocolError:
            pass


def test_fuzz_mutated_headers_are_rejected_or_valid(now):
    rng = random.Random(SEED + 7)
    template = Bundle.create(
        incident_id="i",
        source_node_id="a",
        payload=b"payload",
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
    ).header.to_dict()
    for _ in range(400):
        mutated = dict(template)
        key = rng.choice(list(mutated))
        mutated[key] = random_json_like(rng)
        try:
            header = BundleHeader.from_dict(mutated)
            assert header.protocol_version in ("dmbp/1",)
        except (ProtocolError, TypeError):
            pass


def test_fuzz_truncated_frames_are_rejected(now):
    wire = Bundle.create(
        incident_id="i",
        source_node_id="a",
        payload=b"payload-data",
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
    ).to_wire()
    for cut in range(0, len(wire)):
        try:
            bundle = Bundle.from_wire(wire[:cut])
            bundle.verify_payload()  # a short payload must fail verification
        except ProtocolError:
            pass


def test_fuzz_oversized_metadata_is_rejected(now):
    huge = "x" * 200_000
    d = Bundle.create(
        incident_id="i",
        source_node_id="a",
        payload=b"x",
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
    ).header.to_dict()
    d["category"] = [huge] * 10
    header = BundleHeader.from_dict(d)  # accepted structurally...
    assert len(header.category) == 10
    # ...but the payload cap still bounds what can actually be sent.
    with pytest.raises(ProtocolError):
        Bundle(header=header, payload=b"y" * (8 * 1024 * 1024 + 1))


@pytest.mark.parametrize("value", ["", "NOT_A_TYPE", "p0", 42, None, [], {}])
def test_fuzz_invalid_enum_values_are_rejected(value, now):
    d = Bundle.create(
        incident_id="i",
        source_node_id="a",
        payload=b"x",
        payload_type=PayloadType.INCIDENT_TEXT,
        now=now,
    ).header.to_dict()
    d["priority_class"] = value
    with pytest.raises((ProtocolError, TypeError)):
        BundleHeader.from_dict(d)


def test_fuzz_offer_decoding_never_crashes():
    rng = random.Random(SEED + 8)
    for _ in range(300):
        payload = {
            k: random_json_like(rng)
            for k in [
                "bundle_id",
                "incident_id",
                "payload_type",
                "priority_class",
                "priority_score",
                "size_bytes",
                "sensitivity",
                "expires_at",
            ]
        }
        try:
            BundleOffer.from_dict(payload)
        except ProtocolError:
            pass


def test_fuzz_manifest_policy_never_admits_bad_files():
    rng = random.Random(SEED + 9)
    for _ in range(300):
        manifest = FileManifest(
            file_name="".join(rng.choice(string.printable) for _ in range(8)),
            mime_type=rng.choice(
                ["image/jpeg", "application/x-sh", "", "text/plain", "application/zip"]
            ),
            size_bytes=rng.randint(-10, 20_000_000),
            sha256=rng.choice(["a" * 64, "", "z" * 10]),
        )
        try:
            manifest.validate_policy()
            assert manifest.size_bytes > 0 and len(manifest.sha256) == 64
            assert manifest.mime_type == "image/jpeg"
        except TransferError:
            pass


def test_fuzz_reordered_and_duplicated_events_keep_the_ledger_verifiable(clock):
    from dms.governance.audit import EventLog

    log = EventLog(clock)
    for i in range(20):
        log.append(f"ACTION_{i}", incident_id="i1")
    assert log.verify() is True
    shuffled = list(log.entries)
    random.Random(SEED).shuffle(shuffled)
    assert log.verify(shuffled) is False, "reordering must break the chain"
    assert log.verify(list(log.entries) + [log.entries[0]]) is False, "replay must be visible"
