"""Controlled, versioned enumerations shared across every DisasterMesh module.

Values are wire-stable: they are serialized into DMBP bundles and persisted.
Never rename a member without a protocol version bump and an ADR.
"""

from __future__ import annotations

from enum import Enum

SCHEMA_VERSION = "1.0.0"


class StrEnum(str, Enum):
    """String-valued enum that serializes to its plain value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class Urgency(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class DisasterType(StrEnum):
    FIRE = "FIRE"
    FLOOD = "FLOOD"
    EARTHQUAKE = "EARTHQUAKE"
    BUILDING_COLLAPSE = "BUILDING_COLLAPSE"
    MEDICAL = "MEDICAL"
    LANDSLIDE = "LANDSLIDE"
    ACCIDENT = "ACCIDENT"
    TRAPPED_PERSON = "TRAPPED_PERSON"
    MISSING_PERSON = "MISSING_PERSON"
    LOGISTICS = "LOGISTICS"
    OTHER = "OTHER"


class PriorityClass(StrEnum):
    """Sync queue class. P0 is the only class that may pre-empt everything else."""

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

    @property
    def rank(self) -> int:
        return {"P0": 0, "P1": 1, "P2": 2, "P3": 3}[self.value]


class IncidentStatus(StrEnum):
    DRAFT = "DRAFT"
    QUEUED = "QUEUED"
    RELAYED = "RELAYED"
    RECEIVED = "RECEIVED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISPATCH_REQUESTED = "DISPATCH_REQUESTED"
    DISPATCHED = "DISPATCHED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    RESOLVED = "RESOLVED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    AI_CLASSIFIED = "AI_CLASSIFIED"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    DISPUTED = "DISPUTED"


class PayloadType(StrEnum):
    """What a DMBP bundle carries. TEXT is always independent of media."""

    INCIDENT_TEXT = "INCIDENT_TEXT"
    INCIDENT_UPDATE = "INCIDENT_UPDATE"
    ATTACHMENT_MANIFEST = "ATTACHMENT_MANIFEST"
    ATTACHMENT_CHUNK = "ATTACHMENT_CHUNK"
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
    DISPATCH_ORDER = "DISPATCH_ORDER"
    EVENT_LOG = "EVENT_LOG"


class AttachmentKind(StrEnum):
    IMAGE = "IMAGE"
    AUDIO = "AUDIO"
    DOCUMENT = "DOCUMENT"


class TransferState(StrEnum):
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    TRANSFERRING = "TRANSFERRING"
    PAUSED = "PAUSED"
    INTERRUPTED = "INTERRUPTED"
    VERIFYING = "VERIFYING"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class Role(StrEnum):
    CITIZEN_REPORTER = "CITIZEN_REPORTER"
    VOLUNTEER_RELAY = "VOLUNTEER_RELAY"
    EVENT_COORDINATOR = "EVENT_COORDINATOR"
    MEDICAL_RESPONDER = "MEDICAL_RESPONDER"
    FLOOD_RESPONDER = "FLOOD_RESPONDER"
    GOVERNMENT_AUTHORITY = "GOVERNMENT_AUTHORITY"
    SYSTEM_ADMINISTRATOR = "SYSTEM_ADMINISTRATOR"


class Permission(StrEnum):
    CREATE_INCIDENT = "CREATE_INCIDENT"
    FORWARD_BUNDLE = "FORWARD_BUNDLE"
    VIEW_INCIDENT = "VIEW_INCIDENT"
    VIEW_MEDICAL_DATA = "VIEW_MEDICAL_DATA"
    VIEW_PRECISE_LOCATION = "VIEW_PRECISE_LOCATION"
    PUBLISH_ALERT = "PUBLISH_ALERT"
    ASSIGN_RESOURCE = "ASSIGN_RESOURCE"
    CLOSE_INCIDENT = "CLOSE_INCIDENT"
    EXPORT_AUDIT = "EXPORT_AUDIT"
    REVOKE_NODE = "REVOKE_NODE"


class Sensitivity(StrEnum):
    """Access class of a payload. Relays may carry, but not read, anything above PUBLIC."""

    PUBLIC = "PUBLIC"
    OPERATIONAL = "OPERATIONAL"
    MEDICAL = "MEDICAL"


class ConditionType(StrEnum):
    TRAPPED = "TRAPPED"
    MISSING = "MISSING"
    DEAD = "DEAD"
    UNCONSCIOUS = "UNCONSCIOUS"
    BLEEDING = "BLEEDING"
    NOT_BREATHING = "NOT_BREATHING"
    INJURY = "INJURY"
    OTHER = "OTHER"


class EntityType(StrEnum):
    PEOPLE_COUNT = "PEOPLE_COUNT"
    INJURY = "INJURY"
    CONDITION = "CONDITION"
    TRAPPED = "TRAPPED"
    MISSING = "MISSING"
    DEAD = "DEAD"
    UNCONSCIOUS = "UNCONSCIOUS"
    BLEEDING = "BLEEDING"
    RESOURCE_REQUEST = "RESOURCE_REQUEST"
    LOCATION_HINT = "LOCATION_HINT"
    HAZARD = "HAZARD"
    TIME_REFERENCE = "TIME_REFERENCE"


class ResourceKind(StrEnum):
    AMBULANCE = "AMBULANCE"
    RESCUE_BOAT = "RESCUE_BOAT"
    FIRE_UNIT = "FIRE_UNIT"
    MEDICAL_TEAM = "MEDICAL_TEAM"
    SEARCH_TEAM = "SEARCH_TEAM"
    SHELTER = "SHELTER"
    SUPPLY_TRUCK = "SUPPLY_TRUCK"


class ResourceStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    ASSIGNED = "ASSIGNED"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"


class DispatchStatus(StrEnum):
    RECOMMENDED = "RECOMMENDED"
    ASSIGNED = "ASSIGNED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ClusterDecision(StrEnum):
    MERGE = "MERGE"
    LINK = "LINK"
    KEEP_SEPARATE = "KEEP_SEPARATE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class Provenance(StrEnum):
    """Who produced a value. Human decisions must stay distinguishable from AI ones."""

    HUMAN_REPORTED = "HUMAN_REPORTED"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"
    MACHINE_GENERATED = "MACHINE_GENERATED"
    RULE_ENGINE = "RULE_ENGINE"
    IMPORTED = "IMPORTED"
