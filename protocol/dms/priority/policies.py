"""Context-switching sync policies.

Data-driven: a policy is a row, not a branch. Each selection carries a policy version
and a human-readable explanation, so a coordinator can always ask "why did the image
wait?" and get an answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..domain.enums import DisasterType, PayloadType, PriorityClass, Role

POLICY_SET_VERSION = "context-policy-1.0.0"

LOW_BATTERY_THRESHOLD = 0.20
CRITICAL_BATTERY_THRESHOLD = 0.10


@dataclass(frozen=True)
class SyncContext:
    """Everything that can change how an object is scheduled."""

    receiver_role: Role = Role.EVENT_COORDINATOR
    battery: float = 1.0
    free_storage_bytes: int = 10 * 1024 * 1024 * 1024
    online: bool = False
    incident_age_seconds: float = 0.0
    now: datetime | None = None


@dataclass(frozen=True)
class ContextPolicy:
    """One named behavior row."""

    name: str
    payload_order: tuple[PayloadType, ...]
    require_ack: bool
    replication_bonus: int
    allow_public_alert: bool
    explanation: str
    version: str = POLICY_SET_VERSION


MEDICAL_P0 = ContextPolicy(
    name="medical_p0",
    payload_order=(
        PayloadType.INCIDENT_TEXT,
        PayloadType.INCIDENT_UPDATE,
        PayloadType.ATTACHMENT_MANIFEST,
        PayloadType.ATTACHMENT_CHUNK,
    ),
    require_ack=True,
    replication_bonus=2,
    allow_public_alert=False,
    explanation="Medical P0: text and location go first, image follows, audio last "
    "unless a medical responder asks for it. Acknowledgement required.",
)

FLOOD_P1 = ContextPolicy(
    name="flood_p1",
    payload_order=(
        PayloadType.INCIDENT_TEXT,
        PayloadType.ATTACHMENT_MANIFEST,
        PayloadType.ATTACHMENT_CHUNK,
        PayloadType.INCIDENT_UPDATE,
    ),
    require_ack=True,
    replication_bonus=1,
    allow_public_alert=False,
    explanation="Flood P1: text and location immediately, image next, routed to flood "
    "responders and coordinators, preferring gateway-capable nodes.",
)

ROUTINE_LOGISTICS = ContextPolicy(
    name="routine_logistics",
    payload_order=(PayloadType.INCIDENT_TEXT, PayloadType.ATTACHMENT_MANIFEST),
    require_ack=False,
    replication_bonus=0,
    allow_public_alert=False,
    explanation="Routine logistics: background sync, low replication, no public alert.",
)

DEFAULT_POLICY = ContextPolicy(
    name="default",
    payload_order=(
        PayloadType.INCIDENT_TEXT,
        PayloadType.INCIDENT_UPDATE,
        PayloadType.ATTACHMENT_MANIFEST,
        PayloadType.ATTACHMENT_CHUNK,
    ),
    require_ack=False,
    replication_bonus=0,
    allow_public_alert=False,
    explanation="Default: text before media, no acknowledgement requirement.",
)


def select_policy(
    priority: PriorityClass, disaster_types: tuple[DisasterType, ...]
) -> ContextPolicy:
    """Pick the behavior row for this incident. Deterministic and explainable."""
    types = set(disaster_types)
    if priority is PriorityClass.P0 and (
        DisasterType.MEDICAL in types or DisasterType.TRAPPED_PERSON in types
    ):
        return MEDICAL_P0
    if priority is PriorityClass.P1 and DisasterType.FLOOD in types:
        return FLOOD_P1
    if priority in (PriorityClass.P2, PriorityClass.P3) and (
        DisasterType.LOGISTICS in types or DisasterType.OTHER in types or not types
    ):
        return ROUTINE_LOGISTICS
    return DEFAULT_POLICY


def battery_allows(priority: PriorityClass, ctx: SyncContext) -> tuple[bool, str]:
    """Shed non-critical traffic first as battery falls. P0 text is shed last."""
    if ctx.battery <= CRITICAL_BATTERY_THRESHOLD:
        if priority is PriorityClass.P0:
            return True, "battery critical but P0 always allowed"
        return False, f"battery {ctx.battery:.0%} below critical threshold"
    if ctx.battery <= LOW_BATTERY_THRESHOLD:
        if priority in (PriorityClass.P0, PriorityClass.P1):
            return True, f"battery low ({ctx.battery:.0%}) but {priority.value} allowed"
        return False, f"battery {ctx.battery:.0%} low — deferring {priority.value}"
    return True, "battery sufficient"
