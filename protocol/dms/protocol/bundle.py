"""DisasterMesh Bundle Protocol (DMBP) — transport-independent.

A bundle is an immutable header plus an opaque payload. The header is canonically
serialized (sorted keys, no whitespace, UTF-8) so that a hash or signature computed
on one node reproduces byte-for-byte on another.

Invariants enforced here:
  1. bundle id and payload hash are immutable after construction;
  2. hop count never decreases;
  3. an expired bundle is never forwarded;
  4. a corrupted payload is rejected before storage;
  5. an unknown protocol version fails closed;
  6. critical text is a bundle in its own right, independent of attachments.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from ..domain.clock import utc
from ..domain.enums import (
    PayloadType,
    PriorityClass,
    Role,
    Sensitivity,
)
from ..domain.errors import ProtocolError
from ..domain.models import new_id

PROTOCOL_VERSION = "dmbp/1"
SUPPORTED_VERSIONS = frozenset({PROTOCOL_VERSION})
MAX_PAYLOAD_BYTES = 8 * 1024 * 1024


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


@dataclass(frozen=True)
class BundleHeader:
    """Immutable routing and policy metadata. Frozen: mutation returns a new header."""

    bundle_id: str
    incident_id: str
    source_node_id: str
    payload_type: PayloadType
    payload_size: int
    payload_hash: str
    created_at: datetime
    expires_at: datetime
    priority_class: PriorityClass = PriorityClass.P3
    priority_score: int = 0
    organization_id: str | None = None
    destination_node_id: str | None = None
    role_scope: tuple[Role, ...] = ()
    sensitivity: Sensitivity = Sensitivity.OPERATIONAL
    category: tuple[str, ...] = ()
    hop_limit: int = 6
    hop_count: int = 0
    replication_limit: int = 4
    replication_count: int = 0
    path: tuple[str, ...] = ()
    protocol_version: str = PROTOCOL_VERSION
    signature: str | None = None
    signer_node_id: str | None = None
    encryption: dict[str, Any] = field(default_factory=dict)
    requires_ack: bool = False

    def signable(self) -> dict[str, Any]:
        """Header fields covered by the signature.

        Mutable relay state (hop_count, replication_count, path, signature) is
        excluded: relays legitimately update those without invalidating the source
        signature. Everything a receiver trusts is inside.
        """
        return {
            "bundle_id": self.bundle_id,
            "incident_id": self.incident_id,
            "source_node_id": self.source_node_id,
            "payload_type": self.payload_type.value,
            "payload_size": self.payload_size,
            "payload_hash": self.payload_hash,
            "created_at": utc(self.created_at).isoformat(),
            "expires_at": utc(self.expires_at).isoformat(),
            "priority_class": self.priority_class.value,
            "priority_score": self.priority_score,
            "organization_id": self.organization_id,
            "destination_node_id": self.destination_node_id,
            "role_scope": [r.value for r in self.role_scope],
            "sensitivity": self.sensitivity.value,
            "category": list(self.category),
            "hop_limit": self.hop_limit,
            "replication_limit": self.replication_limit,
            "protocol_version": self.protocol_version,
            "encryption": self.encryption,
            "requires_ack": self.requires_ack,
        }

    def to_dict(self) -> dict[str, Any]:
        d = self.signable()
        d.update(
            {
                "hop_count": self.hop_count,
                "replication_count": self.replication_count,
                "path": list(self.path),
                "signature": self.signature,
                "signer_node_id": self.signer_node_id,
            }
        )
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BundleHeader:
        version = d.get("protocol_version")
        if version not in SUPPORTED_VERSIONS:
            raise ProtocolError(f"unsupported protocol version: {version!r}")
        try:
            return cls(
                bundle_id=d["bundle_id"],
                incident_id=d["incident_id"],
                source_node_id=d["source_node_id"],
                payload_type=PayloadType(d["payload_type"]),
                payload_size=int(d["payload_size"]),
                payload_hash=d["payload_hash"],
                created_at=datetime.fromisoformat(d["created_at"]),
                expires_at=datetime.fromisoformat(d["expires_at"]),
                priority_class=PriorityClass(d["priority_class"]),
                priority_score=int(d.get("priority_score", 0)),
                organization_id=d.get("organization_id"),
                destination_node_id=d.get("destination_node_id"),
                role_scope=tuple(Role(r) for r in d.get("role_scope", [])),
                sensitivity=Sensitivity(d.get("sensitivity", "OPERATIONAL")),
                category=tuple(d.get("category", [])),
                hop_limit=int(d.get("hop_limit", 6)),
                hop_count=int(d.get("hop_count", 0)),
                replication_limit=int(d.get("replication_limit", 4)),
                replication_count=int(d.get("replication_count", 0)),
                path=tuple(d.get("path", [])),
                protocol_version=version,
                signature=d.get("signature"),
                signer_node_id=d.get("signer_node_id"),
                encryption=d.get("encryption", {}) or {},
                requires_ack=bool(d.get("requires_ack", False)),
            )
        except ProtocolError:
            raise
        except (KeyError, ValueError, TypeError) as exc:
            raise ProtocolError(f"malformed bundle header: {exc}") from exc


@dataclass(frozen=True)
class Bundle:
    """Header plus opaque (usually encrypted) payload bytes."""

    header: BundleHeader
    payload: bytes

    @property
    def id(self) -> str:
        return self.header.bundle_id

    def __post_init__(self) -> None:
        if len(self.payload) > MAX_PAYLOAD_BYTES:
            raise ProtocolError(f"payload {len(self.payload)}B exceeds limit {MAX_PAYLOAD_BYTES}B")

    # ------------------------------------------------------------- construction

    @classmethod
    def create(
        cls,
        *,
        incident_id: str,
        source_node_id: str,
        payload: bytes,
        payload_type: PayloadType,
        now: datetime,
        ttl_seconds: int = 3600,
        priority_class: PriorityClass = PriorityClass.P3,
        priority_score: int = 0,
        **kwargs: Any,
    ) -> Bundle:
        header = BundleHeader(
            bundle_id=new_id("bdl"),
            incident_id=incident_id,
            source_node_id=source_node_id,
            payload_type=payload_type,
            payload_size=len(payload),
            payload_hash=sha256_hex(payload),
            created_at=utc(now),
            expires_at=utc(now) + timedelta(seconds=ttl_seconds),
            priority_class=priority_class,
            priority_score=priority_score,
            path=(source_node_id,),
            **kwargs,
        )
        return cls(header=header, payload=payload)

    # -------------------------------------------------------------- validation

    def verify_payload(self) -> None:
        """Reject a corrupted or size-mismatched payload."""
        if len(self.payload) != self.header.payload_size:
            raise ProtocolError(
                f"payload size mismatch: header {self.header.payload_size}, "
                f"actual {len(self.payload)}"
            )
        if sha256_hex(self.payload) != self.header.payload_hash:
            raise ProtocolError("payload hash mismatch — bundle corrupted or tampered")

    def is_expired(self, now: datetime) -> bool:
        return utc(self.header.expires_at) <= utc(now)

    def hops_exhausted(self) -> bool:
        return self.header.hop_count >= self.header.hop_limit

    def replication_exhausted(self) -> bool:
        return self.header.replication_count >= self.header.replication_limit

    def can_forward(self, now: datetime) -> tuple[bool, str]:
        """Whether this bundle may be relayed, and why not when it may not."""
        if self.is_expired(now):
            return False, "expired"
        if self.hops_exhausted():
            return False, "hop_limit_reached"
        if self.replication_exhausted():
            return False, "replication_limit_reached"
        return True, "ok"

    def validate(self, now: datetime) -> None:
        """Full receive-side check. Raises ProtocolError on any violation."""
        if self.header.protocol_version not in SUPPORTED_VERSIONS:
            raise ProtocolError(f"unsupported version {self.header.protocol_version}")
        if self.header.hop_count < 0 or self.header.hop_count > self.header.hop_limit:
            raise ProtocolError("hop count out of range")
        self.verify_payload()
        if self.is_expired(now):
            raise ProtocolError("bundle expired")

    # ----------------------------------------------------------------- routing

    def forwarded(self, to_node_id: str, now: datetime) -> Bundle:
        """Return a copy advanced by one hop toward ``to_node_id``.

        ``path`` records the route the bundle travelled — the originator followed by
        each node that received it — so a coordinator can read "A → B → C" and see
        exactly which devices carried the report. The original is never mutated.
        """
        ok, reason = self.can_forward(now)
        if not ok:
            raise ProtocolError(f"cannot forward bundle {self.id}: {reason}")
        new_header = replace(
            self.header,
            hop_count=self.header.hop_count + 1,
            replication_count=self.header.replication_count + 1,
            path=self.header.path + (to_node_id,),
        )
        return Bundle(header=new_header, payload=self.payload)

    # ----------------------------------------------------------- serialization

    def to_wire(self) -> bytes:
        """Canonical wire form: length-prefixed header JSON, then raw payload."""
        header_bytes = canonical_json(self.header.to_dict())
        return len(header_bytes).to_bytes(4, "big") + header_bytes + self.payload

    @classmethod
    def from_wire(cls, data: bytes) -> Bundle:
        if len(data) < 4:
            raise ProtocolError("truncated bundle frame")
        header_len = int.from_bytes(data[:4], "big")
        if header_len <= 0 or 4 + header_len > len(data):
            raise ProtocolError("invalid header length prefix")
        try:
            header_dict = json.loads(data[4 : 4 + header_len].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError(f"unparsable bundle header: {exc}") from exc
        if not isinstance(header_dict, dict):
            raise ProtocolError("bundle header must be a JSON object")
        header = BundleHeader.from_dict(header_dict)
        payload = data[4 + header_len :]
        return cls(header=header, payload=payload)
