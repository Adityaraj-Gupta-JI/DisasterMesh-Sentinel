"""Bundle inventory exchange — transport independent.

Two nodes compare what they hold, then the sender offers only what the receiver
lacks and is allowed to have. Offers carry routing metadata (priority, size, type)
and never the content itself, so a node learns nothing sensitive by listening.

The digest is an exact id list for the MVP, behind an interface so a Bloom filter
can replace it later without touching the exchange.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..domain.enums import PayloadType, PriorityClass, Role, Sensitivity
from ..domain.errors import ProtocolError

INVENTORY_VERSION = "dmbp-inv/1"


class InventoryDigest(Protocol):
    """Set membership over bundle ids."""

    def contains(self, bundle_id: str) -> bool: ...
    def to_dict(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ExactDigest:
    """Exact id list. Precise, and small enough for hackathon-scale meshes."""

    bundle_ids: frozenset[str] = frozenset()

    def contains(self, bundle_id: str) -> bool:
        return bundle_id in self.bundle_ids

    def to_dict(self) -> dict[str, Any]:
        return {"kind": "exact", "bundle_ids": sorted(self.bundle_ids)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExactDigest:
        if d.get("kind") != "exact":
            raise ProtocolError(f"unsupported digest kind {d.get('kind')!r}")
        return cls(frozenset(d.get("bundle_ids", [])))


@dataclass(frozen=True)
class BundleOffer:
    """Metadata only. Enough to schedule, not enough to leak."""

    bundle_id: str
    incident_id: str
    payload_type: PayloadType
    priority_class: PriorityClass
    priority_score: int
    size_bytes: int
    sensitivity: Sensitivity
    expires_at: str
    requires_ack: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "incident_id": self.incident_id,
            "payload_type": self.payload_type.value,
            "priority_class": self.priority_class.value,
            "priority_score": self.priority_score,
            "size_bytes": self.size_bytes,
            "sensitivity": self.sensitivity.value,
            "expires_at": self.expires_at,
            "requires_ack": self.requires_ack,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BundleOffer:
        try:
            return cls(
                bundle_id=d["bundle_id"],
                incident_id=d["incident_id"],
                payload_type=PayloadType(d["payload_type"]),
                priority_class=PriorityClass(d["priority_class"]),
                priority_score=int(d["priority_score"]),
                size_bytes=int(d["size_bytes"]),
                sensitivity=Sensitivity(d["sensitivity"]),
                expires_at=d["expires_at"],
                requires_ack=bool(d.get("requires_ack", False)),
            )
        except (KeyError, ValueError) as exc:
            raise ProtocolError(f"malformed bundle offer: {exc}") from exc


class MessageType:
    INVENTORY_REQUEST = "INVENTORY_REQUEST"
    INVENTORY_RESPONSE = "INVENTORY_RESPONSE"
    BUNDLE_OFFER = "BUNDLE_OFFER"
    BUNDLE_ACCEPT = "BUNDLE_ACCEPT"
    BUNDLE_RECEIPT = "BUNDLE_RECEIPT"
    BUNDLE_REJECT = "BUNDLE_REJECT"
    BUNDLE_DATA = "BUNDLE_DATA"


@dataclass(frozen=True)
class ControlMessage:
    """A JSON control frame. Bundle payloads travel as their own framed bytes."""

    type: str
    node_id: str
    role: Role
    body: dict[str, Any] = field(default_factory=dict)
    version: str = INVENTORY_VERSION

    def encode(self) -> bytes:
        return b"CTRL" + json.dumps(
            {
                "type": self.type,
                "node_id": self.node_id,
                "role": self.role.value,
                "version": self.version,
                "body": self.body,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def is_control(data: bytes) -> bool:
        return data[:4] == b"CTRL"

    @classmethod
    def decode(cls, data: bytes) -> ControlMessage:
        if not cls.is_control(data):
            raise ProtocolError("not a control frame")
        try:
            d = json.loads(data[4:].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError(f"unparsable control frame: {exc}") from exc
        if not isinstance(d, dict):
            raise ProtocolError("control frame must be a JSON object")
        if d.get("version") != INVENTORY_VERSION:
            raise ProtocolError(f"unsupported inventory version {d.get('version')!r}")
        try:
            return cls(
                type=d["type"],
                node_id=d["node_id"],
                role=Role(d["role"]),
                body=d.get("body", {}),
                version=d["version"],
            )
        except (KeyError, ValueError) as exc:
            raise ProtocolError(f"malformed control frame: {exc}") from exc


def missing_from(theirs: InventoryDigest, mine: list[str]) -> list[str]:
    """Which of my bundle ids the peer does not have."""
    return [bid for bid in mine if not theirs.contains(bid)]
