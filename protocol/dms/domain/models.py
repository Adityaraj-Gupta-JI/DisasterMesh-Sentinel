"""Canonical DisasterMesh Sentinel domain model.

Rules enforced here:
  * every entity has a stable id, creation time, and provenance;
  * unknown values are represented explicitly, never guessed;
  * original user input is preserved verbatim and is never overwritten by AI;
  * nothing in this module imports transport, Android, storage, or UI types.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from .clock import utc
from .enums import (
    SCHEMA_VERSION,
    AttachmentKind,
    ClusterDecision,
    ConditionType,
    DisasterType,
    DispatchStatus,
    EntityType,
    IncidentStatus,
    PayloadType,
    Permission,
    PriorityClass,
    Provenance,
    ResourceKind,
    ResourceStatus,
    Role,
    Sensitivity,
    Urgency,
    VerificationStatus,
)
from .errors import ValidationError


def new_id(prefix: str) -> str:
    """Stable, collision-free identifier. Prefixed so logs stay readable."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


# ---------------------------------------------------------------- value objects


@dataclass(frozen=True)
class Quantity:
    """A count that may be unknown or approximate.

    A vague phrase ("some people") must never become an exact number: it yields
    ``value=None, approximate=True`` with the raw span preserved.
    """

    value: int | None = None
    raw: str | None = None
    approximate: bool = False
    confidence: float | None = None

    @property
    def is_unknown(self) -> bool:
        return self.value is None

    def __post_init__(self) -> None:
        _require(self.value is None or self.value >= 0, "quantity cannot be negative")
        _require(
            self.confidence is None or 0.0 <= self.confidence <= 1.0,
            "confidence must be within 0..1",
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def unknown(cls, raw: str | None = None) -> Quantity:
        return cls(value=None, raw=raw, approximate=True)


@dataclass(frozen=True)
class GeoPoint:
    """A location with explicit precision. Precision is never invented."""

    latitude: float
    longitude: float
    accuracy_m: float | None = None
    source: str = "DEVICE_GPS"
    shared_precisely: bool = True

    def __post_init__(self) -> None:
        _require(-90.0 <= self.latitude <= 90.0, "latitude out of range")
        _require(-180.0 <= self.longitude <= 180.0, "longitude out of range")
        _require(self.accuracy_m is None or self.accuracy_m >= 0, "accuracy cannot be negative")

    def coarse(self, decimals: int = 2) -> GeoPoint:
        """Blur to roughly ~1 km for actors without VIEW_PRECISE_LOCATION."""
        return GeoPoint(
            latitude=round(self.latitude, decimals),
            longitude=round(self.longitude, decimals),
            accuracy_m=max(self.accuracy_m or 0.0, 1000.0),
            source=self.source,
            shared_precisely=False,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Condition:
    """An observed human condition extracted from a report."""

    type: ConditionType
    raw: str | None = None
    confidence: float | None = None
    provenance: Provenance = Provenance.MACHINE_GENERATED

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        d["provenance"] = self.provenance.value
        return d


@dataclass(frozen=True)
class ExtractedEntity:
    """One normalized NER span. The raw span is always retained."""

    type: EntityType
    raw: str
    value: str | int | None = None
    confidence: float | None = None
    uncertain: bool = False
    start: int | None = None
    end: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d


@dataclass(frozen=True)
class AccessPolicy:
    """Who may read this incident, and at what fidelity."""

    sensitivity: Sensitivity = Sensitivity.OPERATIONAL
    allowed_roles: tuple[Role, ...] = ()
    organization_id: str | None = None
    precise_location_roles: tuple[Role, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "sensitivity": self.sensitivity.value,
            "allowed_roles": [r.value for r in self.allowed_roles],
            "organization_id": self.organization_id,
            "precise_location_roles": [r.value for r in self.precise_location_roles],
        }


# ------------------------------------------------------------------- identities


@dataclass
class NodeIdentity:
    """A device participating in the mesh."""

    id: str = field(default_factory=lambda: new_id("node"))
    display_name: str = "unnamed-node"
    role: Role = Role.CITIZEN_REPORTER
    organization_id: str | None = None
    public_key: bytes | None = None
    credential_expires_at: datetime | None = None
    revoked: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_active(self, now: datetime) -> bool:
        if self.revoked:
            return False
        if self.credential_expires_at and utc(self.credential_expires_at) <= utc(now):
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "role": self.role.value,
            "organization_id": self.organization_id,
            "revoked": self.revoked,
            "credential_expires_at": _iso(self.credential_expires_at),
            "created_at": _iso(self.created_at),
        }


@dataclass
class Organization:
    id: str = field(default_factory=lambda: new_id("org"))
    name: str = "unnamed-org"
    policy_version: str = "policy-1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "policy_version": self.policy_version,
            "created_at": _iso(self.created_at),
        }


# -------------------------------------------------------------------- incidents


@dataclass
class IncidentClassification:
    """AI or rule output about an incident. Always a recommendation, never a decision."""

    id: str = field(default_factory=lambda: new_id("cls"))
    incident_id: str = ""
    urgency: Urgency = Urgency.UNKNOWN
    disaster_types: tuple[DisasterType, ...] = ()
    severity: int = 0
    confidence: float = 0.0
    safety_flags: tuple[str, ...] = ()
    explanation_features: tuple[str, ...] = ()
    model_name: str = "unknown"
    model_version: str = "unknown"
    input_hash: str | None = None
    provenance: Provenance = Provenance.MACHINE_GENERATED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require(0 <= self.severity <= 100, "severity must be within 0..100")
        _require(0.0 <= self.confidence <= 1.0, "confidence must be within 0..1")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "urgency": self.urgency.value,
            "disaster_types": [d.value for d in self.disaster_types],
            "severity": self.severity,
            "confidence": self.confidence,
            "safety_flags": list(self.safety_flags),
            "explanation_features": list(self.explanation_features),
            "model_name": self.model_name,
            "model_version": self.model_version,
            "input_hash": self.input_hash,
            "provenance": self.provenance.value,
            "created_at": _iso(self.created_at),
        }


@dataclass
class EntityExtraction:
    """Normalized entities for one incident, plus the raw spans they came from."""

    id: str = field(default_factory=lambda: new_id("ent"))
    incident_id: str = ""
    people_affected: Quantity = field(default_factory=Quantity.unknown)
    conditions: tuple[Condition, ...] = ()
    requested_resources: tuple[str, ...] = ()
    location_hints: tuple[str, ...] = ()
    hazards: tuple[str, ...] = ()
    entities: tuple[ExtractedEntity, ...] = ()
    model_name: str = "unknown"
    model_version: str = "unknown"
    provenance: Provenance = Provenance.MACHINE_GENERATED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "people_affected": self.people_affected.to_dict(),
            "conditions": [c.to_dict() for c in self.conditions],
            "requested_resources": list(self.requested_resources),
            "location_hints": list(self.location_hints),
            "hazards": list(self.hazards),
            "entities": [e.to_dict() for e in self.entities],
            "model_name": self.model_name,
            "model_version": self.model_version,
            "provenance": self.provenance.value,
            "created_at": _iso(self.created_at),
        }


@dataclass
class Attachment:
    """Evidence attached to an incident. Content lives on disk, metadata lives here."""

    id: str = field(default_factory=lambda: new_id("att"))
    incident_id: str = ""
    kind: AttachmentKind = AttachmentKind.IMAGE
    file_name: str = "evidence.bin"
    mime_type: str = "application/octet-stream"
    size_bytes: int = 0
    sha256: str = ""
    local_path: str | None = None
    committed: bool = False
    transcript_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require(self.size_bytes >= 0, "attachment size cannot be negative")
        _require(len(self.sha256) in (0, 64), "sha256 must be a 64-char hex digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "kind": self.kind.value,
            "file_name": self.file_name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            # Device-local path. Never travels: bundles carry attachment ids only.
            "local_path": self.local_path,
            "committed": self.committed,
            "transcript_id": self.transcript_id,
            "created_at": _iso(self.created_at),
        }


@dataclass
class Translation:
    """Machine translation of an incident. Never replaces the original text."""

    id: str = field(default_factory=lambda: new_id("tr"))
    incident_id: str = ""
    source_language: str = "und"
    target_language: str = "en"
    text: str = ""
    model_name: str = "mock-translate"
    model_version: str = "0.0.0"
    machine_generated: bool = True
    human_verified: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "text": self.text,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "machine_generated": self.machine_generated,
            "human_verified": self.human_verified,
            "created_at": _iso(self.created_at),
        }


@dataclass
class Incident:
    """The central entity. ``original_text`` is immutable user input."""

    id: str = field(default_factory=lambda: new_id("inc"))
    source_node_id: str = ""
    organization_id: str | None = None
    original_text: str = ""
    source_language: str = "und"
    location: GeoPoint | None = None
    reported_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    disaster_types: tuple[DisasterType, ...] = ()
    urgency: Urgency = Urgency.UNKNOWN
    severity: int = 0
    classification_confidence: float = 0.0
    people_affected: Quantity = field(default_factory=Quantity.unknown)
    conditions: tuple[Condition, ...] = ()
    requested_resources: tuple[str, ...] = ()

    priority_score: int = 0
    priority_class: PriorityClass = PriorityClass.P3
    priority_explanation: tuple[str, ...] = ()
    policy_version: str = "policy-1.0.0"

    status: IncidentStatus = IncidentStatus.DRAFT
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    access_policy: AccessPolicy = field(default_factory=AccessPolicy)
    attachment_ids: tuple[str, ...] = ()
    audio_reference: str | None = None
    cluster_id: str | None = None

    provenance: Provenance = Provenance.HUMAN_REPORTED
    revision: int = 1
    schema_version: str = SCHEMA_VERSION
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require(bool(self.id), "incident requires a stable id")
        _require(bool(self.source_node_id), "incident requires a source node id")
        _require(0 <= self.severity <= 100, "severity must be within 0..100")
        _require(0 <= self.priority_score <= 100, "priority score must be within 0..100")
        _require(self.revision >= 1, "revision starts at 1")
        _require(
            bool(self.original_text.strip()) or self.audio_reference is not None,
            "incident needs original text or an original audio reference",
        )

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and utc(self.expires_at) <= utc(now)

    def touch(self, now: datetime) -> None:
        """Bump revision and updated_at. The only sanctioned mutation entry point."""
        self.revision += 1
        self.updated_at = utc(now)

    def redacted_for(self, *, precise_location: bool, medical: bool) -> Incident:
        """A copy safe to show an actor with the given clearances."""
        from copy import deepcopy

        clone = deepcopy(self)
        if not precise_location and clone.location is not None:
            clone.location = clone.location.coarse()
        if not medical:
            clone.conditions = ()
            clone.people_affected = Quantity.unknown(raw=None)
            if clone.access_policy.sensitivity is Sensitivity.MEDICAL:
                clone.original_text = "[restricted: medical content]"
        return clone

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_node_id": self.source_node_id,
            "organization_id": self.organization_id,
            "original_text": self.original_text,
            "source_language": self.source_language,
            "location": self.location.to_dict() if self.location else None,
            "reported_at": _iso(self.reported_at),
            "expires_at": _iso(self.expires_at),
            "disaster_types": [d.value for d in self.disaster_types],
            "urgency": self.urgency.value,
            "severity": self.severity,
            "classification_confidence": self.classification_confidence,
            "people_affected": self.people_affected.to_dict(),
            "conditions": [c.to_dict() for c in self.conditions],
            "requested_resources": list(self.requested_resources),
            "priority_score": self.priority_score,
            "priority_class": self.priority_class.value,
            "priority_explanation": list(self.priority_explanation),
            "policy_version": self.policy_version,
            "status": self.status.value,
            "verification_status": self.verification_status.value,
            "access_policy": self.access_policy.to_dict(),
            "attachment_ids": list(self.attachment_ids),
            "audio_reference": self.audio_reference,
            "cluster_id": self.cluster_id,
            "provenance": self.provenance.value,
            "revision": self.revision,
            "schema_version": self.schema_version,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


# ------------------------------------------------------- coordination artifacts


@dataclass
class Acknowledgement:
    """A human confirming they have seen an incident. Idempotent by (incident, node)."""

    id: str = field(default_factory=lambda: new_id("ack"))
    incident_id: str = ""
    node_id: str = ""
    actor_role: Role = Role.EVENT_COORDINATOR
    note: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def dedup_key(self) -> str:
        return f"{self.incident_id}:{self.node_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "node_id": self.node_id,
            "actor_role": self.actor_role.value,
            "note": self.note,
            "created_at": _iso(self.created_at),
        }


@dataclass
class Resource:
    """A simulated responder asset. Never a real emergency unit."""

    id: str = field(default_factory=lambda: new_id("res"))
    kind: ResourceKind = ResourceKind.AMBULANCE
    label: str = "unnamed-resource"
    organization_id: str | None = None
    status: ResourceStatus = ResourceStatus.AVAILABLE
    location: GeoPoint | None = None
    capabilities: tuple[DisasterType, ...] = ()
    simulated: bool = True
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "label": self.label,
            "organization_id": self.organization_id,
            "status": self.status.value,
            "location": self.location.to_dict() if self.location else None,
            "capabilities": [c.value for c in self.capabilities],
            "simulated": self.simulated,
            "last_seen_at": _iso(self.last_seen_at),
        }


@dataclass
class DispatchOrder:
    """A simulated assignment authorized by a human coordinator."""

    id: str = field(default_factory=lambda: new_id("dsp"))
    incident_id: str = ""
    resource_id: str = ""
    status: DispatchStatus = DispatchStatus.RECOMMENDED
    recommended_reason: str = ""
    authorized_by_node_id: str | None = None
    authorized_by_role: Role | None = None
    simulated: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "resource_id": self.resource_id,
            "status": self.status.value,
            "recommended_reason": self.recommended_reason,
            "authorized_by_node_id": self.authorized_by_node_id,
            "authorized_by_role": (
                self.authorized_by_role.value if self.authorized_by_role else None
            ),
            "simulated": self.simulated,
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
        }


@dataclass
class Alert:
    """A public alert. Requires PUBLISH_ALERT plus explicit human authorization."""

    id: str = field(default_factory=lambda: new_id("alr"))
    incident_ids: tuple[str, ...] = ()
    headline: str = ""
    body: str = ""
    authorized_by_node_id: str | None = None
    authorized_by_role: Role | None = None
    published: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_ids": list(self.incident_ids),
            "headline": self.headline,
            "body": self.body,
            "authorized_by_node_id": self.authorized_by_node_id,
            "authorized_by_role": (
                self.authorized_by_role.value if self.authorized_by_role else None
            ),
            "published": self.published,
            "created_at": _iso(self.created_at),
        }


@dataclass
class IncidentCluster:
    """A provisional grouping of likely-duplicate reports. Sources are never deleted."""

    id: str = field(default_factory=lambda: new_id("clu"))
    incident_ids: tuple[str, ...] = ()
    decision: ClusterDecision = ClusterDecision.REVIEW_REQUIRED
    similarity: float = 0.0
    embedding_model_version: str = "mock-embed-0.0.0"
    provisional: bool = True
    human_reviewed: bool = False
    rationale: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_ids": list(self.incident_ids),
            "decision": self.decision.value,
            "similarity": self.similarity,
            "embedding_model_version": self.embedding_model_version,
            "provisional": self.provisional,
            "human_reviewed": self.human_reviewed,
            "rationale": list(self.rationale),
            "created_at": _iso(self.created_at),
        }


@dataclass
class EventLogEntry:
    """One tamper-evident audit record. ``prev_hash`` chains the ledger."""

    id: str = field(default_factory=lambda: new_id("evt"))
    incident_id: str | None = None
    actor_node_id: str | None = None
    actor_role: Role | None = None
    action: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    prev_hash: str | None = None
    entry_hash: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "actor_node_id": self.actor_node_id,
            "actor_role": self.actor_role.value if self.actor_role else None,
            "action": self.action,
            "detail": self.detail,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
            "created_at": _iso(self.created_at),
        }


@dataclass
class SyncObject:
    """A transferable unit queued by the Emergency Sync Engine."""

    id: str = field(default_factory=lambda: new_id("syn"))
    bundle_id: str = ""
    incident_id: str = ""
    payload_type: PayloadType = PayloadType.INCIDENT_TEXT
    priority_class: PriorityClass = PriorityClass.P3
    priority_score: int = 0
    size_bytes: int = 0
    sensitivity: Sensitivity = Sensitivity.OPERATIONAL
    allowed_roles: tuple[Role, ...] = ()
    expires_at: datetime | None = None
    requires_ack: bool = False
    delivered_to: tuple[str, ...] = ()
    attempts: int = 0

    @property
    def is_text(self) -> bool:
        return self.payload_type in (
            PayloadType.INCIDENT_TEXT,
            PayloadType.INCIDENT_UPDATE,
            PayloadType.ACKNOWLEDGEMENT,
            PayloadType.DISPATCH_ORDER,
            PayloadType.EVENT_LOG,
        )

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and utc(self.expires_at) <= utc(now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "bundle_id": self.bundle_id,
            "incident_id": self.incident_id,
            "payload_type": self.payload_type.value,
            "priority_class": self.priority_class.value,
            "priority_score": self.priority_score,
            "size_bytes": self.size_bytes,
            "sensitivity": self.sensitivity.value,
            "allowed_roles": [r.value for r in self.allowed_roles],
            "expires_at": _iso(self.expires_at),
            "requires_ack": self.requires_ack,
            "delivered_to": list(self.delivered_to),
            "attempts": self.attempts,
        }


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.CITIZEN_REPORTER: frozenset({Permission.CREATE_INCIDENT, Permission.VIEW_INCIDENT}),
    Role.VOLUNTEER_RELAY: frozenset({Permission.FORWARD_BUNDLE}),
    # A coordinator triages medical P0s and authorizes the ambulance; withholding
    # medical detail here would break the core flow. See ADR-0002 in docs/DECISIONS.md.
    Role.EVENT_COORDINATOR: frozenset(
        {
            Permission.CREATE_INCIDENT,
            Permission.FORWARD_BUNDLE,
            Permission.VIEW_INCIDENT,
            Permission.VIEW_MEDICAL_DATA,
            Permission.VIEW_PRECISE_LOCATION,
            Permission.ASSIGN_RESOURCE,
            Permission.CLOSE_INCIDENT,
        }
    ),
    Role.MEDICAL_RESPONDER: frozenset(
        {
            Permission.VIEW_INCIDENT,
            Permission.VIEW_MEDICAL_DATA,
            Permission.VIEW_PRECISE_LOCATION,
            Permission.FORWARD_BUNDLE,
        }
    ),
    Role.FLOOD_RESPONDER: frozenset(
        {
            Permission.VIEW_INCIDENT,
            Permission.VIEW_PRECISE_LOCATION,
            Permission.FORWARD_BUNDLE,
        }
    ),
    Role.GOVERNMENT_AUTHORITY: frozenset(
        {
            Permission.VIEW_INCIDENT,
            Permission.VIEW_PRECISE_LOCATION,
            Permission.PUBLISH_ALERT,
            Permission.ASSIGN_RESOURCE,
            Permission.CLOSE_INCIDENT,
            Permission.EXPORT_AUDIT,
        }
    ),
    Role.SYSTEM_ADMINISTRATOR: frozenset(
        {
            Permission.VIEW_INCIDENT,
            Permission.EXPORT_AUDIT,
            Permission.REVOKE_NODE,
            Permission.FORWARD_BUNDLE,
        }
    ),
}


def _iso(dt: datetime | None) -> str | None:
    return utc(dt).isoformat() if dt else None
