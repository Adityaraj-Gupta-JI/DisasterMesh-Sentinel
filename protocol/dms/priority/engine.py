"""Deterministic priority engine.

The AI proposes; this module decides. Given the same inputs and the same policy
version it always returns the same score, and every point of that score is explained.

Hard escalation rules cannot be undone by low AI confidence: a rule-triggered
life-threat sets a floor. Only a human coordinator may override, and the override is
recorded with a reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..domain.clock import utc
from ..domain.enums import (
    ConditionType,
    DisasterType,
    PriorityClass,
    Provenance,
    Role,
    Sensitivity,
    Urgency,
)
from ..domain.models import Condition, Quantity

POLICY_VERSION = "policy-1.0.0"

#: Score floors that a rule-triggered condition guarantees, whatever the AI said.
LIFE_THREAT_CONDITIONS = frozenset({ConditionType.NOT_BREATHING, ConditionType.UNCONSCIOUS})
TRAPPED_CONDITIONS = frozenset({ConditionType.TRAPPED})
ACTIVE_HAZARD_TYPES = frozenset(
    {DisasterType.FIRE, DisasterType.FLOOD, DisasterType.BUILDING_COLLAPSE, DisasterType.LANDSLIDE}
)

URGENCY_BASE = {
    Urgency.CRITICAL: 60,
    Urgency.HIGH: 40,
    Urgency.MEDIUM: 20,
    Urgency.LOW: 8,
    Urgency.UNKNOWN: 15,
}

CLASS_THRESHOLDS = ((85, PriorityClass.P0), (60, PriorityClass.P1), (30, PriorityClass.P2))

TTL_SECONDS = {
    PriorityClass.P0: 6 * 3600,
    PriorityClass.P1: 12 * 3600,
    PriorityClass.P2: 24 * 3600,
    PriorityClass.P3: 48 * 3600,
}

REPLICATION_LIMIT = {
    PriorityClass.P0: 8,
    PriorityClass.P1: 6,
    PriorityClass.P2: 3,
    PriorityClass.P3: 2,
}


@dataclass(frozen=True)
class PriorityInputs:
    """Everything the engine is allowed to consider. No model handles, ever."""

    urgency: Urgency = Urgency.UNKNOWN
    severity: int = 0
    disaster_types: tuple[DisasterType, ...] = ()
    confidence: float = 0.0
    people_affected: Quantity = field(default_factory=Quantity.unknown)
    conditions: tuple[Condition, ...] = ()
    hazards: tuple[str, ...] = ()
    message_age_seconds: float = 0.0
    human_verified: bool = False
    ai_available: bool = True
    organization_policy_version: str = POLICY_VERSION


@dataclass(frozen=True)
class PriorityDecision:
    """The engine's output, fully explained."""

    score: int
    priority_class: PriorityClass
    ttl_seconds: int
    replication_limit: int
    allowed_roles: tuple[Role, ...]
    sensitivity: Sensitivity
    requires_ack: bool
    text_before_media: bool
    explanation: tuple[str, ...]
    policy_version: str = POLICY_VERSION
    escalated_by_rule: bool = False
    provenance: Provenance = Provenance.RULE_ENGINE

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "priority_class": self.priority_class.value,
            "ttl_seconds": self.ttl_seconds,
            "replication_limit": self.replication_limit,
            "allowed_roles": [r.value for r in self.allowed_roles],
            "sensitivity": self.sensitivity.value,
            "requires_ack": self.requires_ack,
            "text_before_media": self.text_before_media,
            "explanation": list(self.explanation),
            "policy_version": self.policy_version,
            "escalated_by_rule": self.escalated_by_rule,
        }


def _classify(score: int) -> PriorityClass:
    for threshold, cls in CLASS_THRESHOLDS:
        if score >= threshold:
            return cls
    return PriorityClass.P3


def evaluate(inputs: PriorityInputs) -> PriorityDecision:
    """Score an incident 0..100 and derive its full sync policy."""
    why: list[str] = []
    score = URGENCY_BASE[inputs.urgency]
    why.append(f"urgency {inputs.urgency.value} → base {score}")

    if not inputs.ai_available:
        why.append("AI unavailable → rule-only evaluation")

    severity_points = round(inputs.severity * 0.20)
    score += severity_points
    why.append(f"severity {inputs.severity} → +{severity_points}")

    condition_types = {c.type for c in inputs.conditions}
    floor = 0
    escalated = False

    if condition_types & LIFE_THREAT_CONDITIONS:
        floor = max(floor, 85)
        escalated = True
        why.append("RULE: unconscious/not breathing → P0 floor 85")

    active_hazard = bool(set(inputs.disaster_types) & ACTIVE_HAZARD_TYPES) or bool(inputs.hazards)
    if condition_types & TRAPPED_CONDITIONS:
        if active_hazard:
            floor = max(floor, 85)
            escalated = True
            why.append("RULE: trapped person with active hazard → P0 floor 85")
        else:
            floor = max(floor, 60)
            escalated = True
            why.append("RULE: trapped person → P1 floor 60")

    if DisasterType.FIRE in inputs.disaster_types and (
        not inputs.people_affected.is_unknown or condition_types
    ):
        floor = max(floor, 60)
        escalated = True
        why.append("RULE: active fire near people → P1 floor 60")

    people = inputs.people_affected
    if people.is_unknown:
        why.append("people affected unknown → no adjustment (never guessed)")
    else:
        pts = min(12, (people.value or 0) * 2)
        score += pts
        why.append(f"{people.value} people affected → +{pts}")

    if inputs.human_verified:
        score += 6
        why.append("human verified → +6")
    elif inputs.confidence < 0.5 and not escalated:
        score -= 4
        why.append(f"low AI confidence {inputs.confidence:.2f}, no rule trigger → -4")

    age_minutes = inputs.message_age_seconds / 60.0
    if age_minutes > 60:
        decay = min(10, int((age_minutes - 60) // 30))
        score -= decay
        why.append(f"age {age_minutes:.0f} min → -{decay}")

    score = max(0, min(100, score))
    if floor and score < floor:
        why.append(f"rule floor raised score {score} → {floor}")
        score = floor

    priority = _classify(score)
    medical = DisasterType.MEDICAL in inputs.disaster_types or bool(
        condition_types - {ConditionType.OTHER}
    )
    sensitivity = Sensitivity.MEDICAL if medical else Sensitivity.OPERATIONAL

    allowed: tuple[Role, ...]
    if sensitivity is Sensitivity.MEDICAL:
        allowed = (
            Role.EVENT_COORDINATOR,
            Role.MEDICAL_RESPONDER,
            Role.GOVERNMENT_AUTHORITY,
            Role.VOLUNTEER_RELAY,  # carries ciphertext only; cannot read
        )
        why.append("medical content → restricted roles; relays carry ciphertext only")
    else:
        allowed = ()

    return PriorityDecision(
        score=score,
        priority_class=priority,
        ttl_seconds=TTL_SECONDS[priority],
        replication_limit=REPLICATION_LIMIT[priority],
        allowed_roles=allowed,
        sensitivity=sensitivity,
        requires_ack=priority in (PriorityClass.P0, PriorityClass.P1),
        text_before_media=True,
        explanation=tuple(why),
        escalated_by_rule=escalated,
    )


@dataclass(frozen=True)
class Override:
    """A human coordinator's explicit priority override. Always logged."""

    priority_class: PriorityClass
    reason: str
    actor_node_id: str
    actor_role: Role
    at: datetime

    def apply(self, decision: PriorityDecision) -> PriorityDecision:
        from dataclasses import replace as _replace

        note = (
            f"HUMAN OVERRIDE by {self.actor_role.value} ({self.actor_node_id}) "
            f"→ {self.priority_class.value}: {self.reason}"
        )
        floor_scores = {
            PriorityClass.P0: 85,
            PriorityClass.P1: 60,
            PriorityClass.P2: 30,
            PriorityClass.P3: 10,
        }
        return _replace(
            decision,
            priority_class=self.priority_class,
            score=floor_scores[self.priority_class],
            ttl_seconds=TTL_SECONDS[self.priority_class],
            replication_limit=REPLICATION_LIMIT[self.priority_class],
            requires_ack=self.priority_class in (PriorityClass.P0, PriorityClass.P1),
            explanation=decision.explanation + (note,),
            provenance=Provenance.HUMAN_VERIFIED,
        )


def age_seconds(reported_at: datetime, now: datetime) -> float:
    return max(0.0, (utc(now) - utc(reported_at)).total_seconds())
