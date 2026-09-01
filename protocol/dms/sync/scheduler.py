"""Emergency Sync Engine — scheduling decisions.

Selection is a total order, not a heuristic soup, and every object considered gets a
recorded verdict with a reason. The hard guarantees this module owes the product:

  1. P0 text is never blocked by media;
  2. expired objects are never scheduled;
  3. restricted objects are never offered to unauthorized roles;
  4. a completed object is never retransmitted as new;
  5. low battery sheds non-critical traffic first.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from ..domain.clock import utc
from ..domain.enums import PayloadType, PriorityClass, Role
from ..domain.models import NodeIdentity, SyncObject
from ..governance.authz import can_receive
from ..priority.policies import SyncContext, battery_allows

#: Ordering weight for payload kinds inside one priority class. Lower goes first.
PAYLOAD_ORDER: dict[PayloadType, int] = {
    PayloadType.INCIDENT_TEXT: 0,
    PayloadType.ACKNOWLEDGEMENT: 1,
    PayloadType.INCIDENT_UPDATE: 2,
    PayloadType.DISPATCH_ORDER: 3,
    PayloadType.EVENT_LOG: 4,
    PayloadType.ATTACHMENT_MANIFEST: 5,
    PayloadType.ATTACHMENT_CHUNK: 6,
}

EXPIRY_URGENT_SECONDS = 900.0


@dataclass(frozen=True)
class SchedulingDecision:
    """One observable, explainable verdict."""

    object_id: str
    bundle_id: str
    selected: bool
    reason: str
    priority_class: PriorityClass
    payload_type: PayloadType
    receiver_role: Role
    battery: float
    policy_version: str
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            "object_id": self.object_id,
            "bundle_id": self.bundle_id,
            "selected": self.selected,
            "reason": self.reason,
            "priority_class": self.priority_class.value,
            "payload_type": self.payload_type.value,
            "receiver_role": self.receiver_role.value,
            "battery": self.battery,
            "policy_version": self.policy_version,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SchedulerResult:
    selected: list[SyncObject] = field(default_factory=list)
    decisions: list[SchedulingDecision] = field(default_factory=list)

    def reasons_for(self, object_id: str) -> list[str]:
        return [d.reason for d in self.decisions if d.object_id == object_id]


class SyncScheduler:
    """Chooses what to offer a given peer, in what order."""

    def __init__(self, policy_version: str = "sync-1.0.0") -> None:
        self.policy_version = policy_version
        self.decision_log: list[SchedulingDecision] = []

    # ------------------------------------------------------------------ order

    @staticmethod
    def sort_key(obj: SyncObject, now: datetime) -> tuple:
        """Total order: class, then text-before-media, then score, size, age.

        Payload rank sits above priority score deliberately: within P0 the text of a
        report outranks its own photograph, which is the whole text-first promise.
        """
        expiry_urgency = 0
        if obj.expires_at is not None:
            remaining = (utc(obj.expires_at) - utc(now)).total_seconds()
            expiry_urgency = 0 if remaining <= EXPIRY_URGENT_SECONDS else 1
        return (
            obj.priority_class.rank,
            PAYLOAD_ORDER.get(obj.payload_type, 9),
            expiry_urgency,
            -obj.priority_score,
            obj.size_bytes,
            obj.attempts,
        )

    # --------------------------------------------------------------- selection

    def select(
        self,
        objects: Iterable[SyncObject],
        *,
        receiver: NodeIdentity,
        now: datetime,
        context: SyncContext | None = None,
        max_objects: int | None = None,
        max_bytes: int | None = None,
    ) -> SchedulerResult:
        """Pick the objects to offer ``receiver`` right now, best first."""
        ctx = context or SyncContext(receiver_role=receiver.role)
        result = SchedulerResult()
        candidates = sorted(objects, key=lambda o: self.sort_key(o, now))
        budget_bytes = max_bytes
        p0_text_pending = any(
            o.priority_class is PriorityClass.P0
            and o.payload_type is PayloadType.INCIDENT_TEXT
            and receiver.id not in o.delivered_to
            for o in candidates
        )

        for obj in candidates:
            verdict: tuple[bool, str]

            if receiver.id in obj.delivered_to:
                verdict = (False, "already_delivered_to_receiver")
            elif obj.is_expired(now):
                verdict = (False, "expired")
            else:
                allowed, why = can_receive(obj, receiver, now=now)
                if not allowed:
                    verdict = (False, why)
                else:
                    battery_ok, battery_why = battery_allows(obj.priority_class, ctx)
                    if not battery_ok:
                        verdict = (False, battery_why)
                    elif (
                        p0_text_pending
                        and not obj.is_text
                        and obj.priority_class is not PriorityClass.P0
                    ):
                        # Media never overtakes an undelivered P0 text.
                        verdict = (False, "deferred_behind_pending_p0_text")
                    elif max_objects is not None and len(result.selected) >= max_objects:
                        verdict = (False, "object_budget_exhausted")
                    elif budget_bytes is not None and obj.size_bytes > budget_bytes:
                        if obj.priority_class is PriorityClass.P0 and obj.is_text:
                            verdict = (True, "p0_text_exempt_from_byte_budget")
                        else:
                            verdict = (False, "byte_budget_exhausted")
                    else:
                        verdict = (True, "selected")

            selected, reason = verdict
            if selected:
                result.selected.append(obj)
                if budget_bytes is not None:
                    budget_bytes = max(0, budget_bytes - obj.size_bytes)
                if (
                    obj.priority_class is PriorityClass.P0
                    and obj.payload_type is PayloadType.INCIDENT_TEXT
                ):
                    p0_text_pending = False

            decision = SchedulingDecision(
                object_id=obj.id,
                bundle_id=obj.bundle_id,
                selected=selected,
                reason=reason,
                priority_class=obj.priority_class,
                payload_type=obj.payload_type,
                receiver_role=receiver.role,
                battery=ctx.battery,
                policy_version=self.policy_version,
                timestamp=utc(now),
            )
            result.decisions.append(decision)
            self.decision_log.append(decision)

        return result
