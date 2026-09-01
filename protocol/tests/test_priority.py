"""Priority engine: determinism, explainability, and the hard escalation floors."""

from __future__ import annotations

import pytest
from dms.domain.enums import (
    ConditionType,
    DisasterType,
    PriorityClass,
    Role,
    Sensitivity,
    Urgency,
)
from dms.domain.models import Condition, Quantity
from dms.priority.engine import Override, PriorityInputs, evaluate
from dms.priority.policies import (
    FLOOD_P1,
    MEDICAL_P0,
    ROUTINE_LOGISTICS,
    SyncContext,
    battery_allows,
    select_policy,
)


def test_collapse_with_trapped_people_is_p0():
    d = evaluate(
        PriorityInputs(
            urgency=Urgency.CRITICAL,
            severity=85,
            confidence=0.9,
            disaster_types=(DisasterType.BUILDING_COLLAPSE, DisasterType.TRAPPED_PERSON),
            conditions=(Condition(type=ConditionType.TRAPPED),),
            people_affected=Quantity(value=3, raw="Three people"),
        )
    )
    assert d.priority_class is PriorityClass.P0
    assert d.score == 85
    assert d.requires_ack and d.text_before_media


def test_routine_water_request_is_p3():
    d = evaluate(
        PriorityInputs(
            urgency=Urgency.LOW,
            severity=12,
            confidence=0.8,
            disaster_types=(DisasterType.LOGISTICS,),
        )
    )
    assert d.priority_class is PriorityClass.P3
    assert not d.requires_ack


def test_ai_uncertainty_cannot_downgrade_a_rule_triggered_life_threat():
    """The single most important safety property in the engine."""
    confident = evaluate(
        PriorityInputs(
            urgency=Urgency.CRITICAL,
            severity=90,
            confidence=0.95,
            conditions=(Condition(type=ConditionType.NOT_BREATHING),),
        )
    )
    uncertain = evaluate(
        PriorityInputs(
            urgency=Urgency.LOW,
            severity=5,
            confidence=0.02,
            conditions=(Condition(type=ConditionType.NOT_BREATHING),),
        )
    )
    assert confident.priority_class is PriorityClass.P0
    assert uncertain.priority_class is PriorityClass.P0
    assert uncertain.escalated_by_rule
    assert any("RULE" in e for e in uncertain.explanation)


def test_trapped_without_hazard_floors_at_p1_and_with_hazard_at_p0():
    no_hazard = evaluate(
        PriorityInputs(
            urgency=Urgency.MEDIUM,
            severity=30,
            conditions=(Condition(type=ConditionType.TRAPPED),),
        )
    )
    with_hazard = evaluate(
        PriorityInputs(
            urgency=Urgency.MEDIUM,
            severity=30,
            disaster_types=(DisasterType.FIRE,),
            conditions=(Condition(type=ConditionType.TRAPPED),),
        )
    )
    assert no_hazard.priority_class is PriorityClass.P1
    assert with_hazard.priority_class is PriorityClass.P0


def test_unknown_people_count_never_adds_points():
    unknown = evaluate(PriorityInputs(urgency=Urgency.HIGH, severity=50))
    known = evaluate(
        PriorityInputs(
            urgency=Urgency.HIGH,
            severity=50,
            people_affected=Quantity(value=4, raw="four"),
        )
    )
    assert known.score > unknown.score
    assert any("unknown" in e for e in unknown.explanation)


def test_evaluation_is_deterministic():
    args = PriorityInputs(
        urgency=Urgency.HIGH,
        severity=64,
        confidence=0.71,
        disaster_types=(DisasterType.FLOOD,),
        people_affected=Quantity(value=2),
    )
    assert [evaluate(args).score for _ in range(10)] == [evaluate(args).score] * 10


def test_every_decision_is_explained():
    d = evaluate(PriorityInputs(urgency=Urgency.HIGH, severity=55))
    assert len(d.explanation) >= 2
    assert d.policy_version


def test_medical_content_is_restricted_to_cleared_roles():
    d = evaluate(
        PriorityInputs(
            urgency=Urgency.CRITICAL,
            severity=90,
            conditions=(Condition(type=ConditionType.BLEEDING),),
        )
    )
    assert d.sensitivity is Sensitivity.MEDICAL
    assert Role.EVENT_COORDINATOR in d.allowed_roles
    assert Role.CITIZEN_REPORTER not in d.allowed_roles


def test_ai_unavailable_is_recorded_and_still_produces_a_decision():
    d = evaluate(PriorityInputs(urgency=Urgency.HIGH, severity=50, ai_available=False))
    assert d.priority_class in tuple(PriorityClass)
    assert any("AI unavailable" in e for e in d.explanation)


def test_age_decays_priority():
    fresh = evaluate(PriorityInputs(urgency=Urgency.HIGH, severity=50))
    stale = evaluate(
        PriorityInputs(urgency=Urgency.HIGH, severity=50, message_age_seconds=6 * 3600)
    )
    assert stale.score < fresh.score


def test_human_override_is_recorded_with_its_reason(now):
    base = evaluate(PriorityInputs(urgency=Urgency.LOW, severity=10))
    overridden = Override(
        priority_class=PriorityClass.P0,
        reason="caller confirmed by radio",
        actor_node_id="C",
        actor_role=Role.EVENT_COORDINATOR,
        at=now,
    ).apply(base)
    assert overridden.priority_class is PriorityClass.P0
    assert any("HUMAN OVERRIDE" in e and "radio" in e for e in overridden.explanation)


def test_ttl_and_replication_scale_with_priority():
    p0 = evaluate(PriorityInputs(urgency=Urgency.CRITICAL, severity=95))
    p3 = evaluate(PriorityInputs(urgency=Urgency.LOW, severity=5))
    assert p0.ttl_seconds < p3.ttl_seconds, "critical data should not linger for days"
    assert p0.replication_limit > p3.replication_limit


@pytest.mark.parametrize(
    "priority,types,expected",
    [
        (PriorityClass.P0, (DisasterType.MEDICAL,), MEDICAL_P0),
        (PriorityClass.P1, (DisasterType.FLOOD,), FLOOD_P1),
        (PriorityClass.P3, (DisasterType.LOGISTICS,), ROUTINE_LOGISTICS),
    ],
)
def test_context_policy_selection(priority, types, expected):
    assert select_policy(priority, types) is expected
    assert select_policy(priority, types).explanation


def test_low_battery_sheds_non_critical_first():
    low = SyncContext(battery=0.15)
    assert battery_allows(PriorityClass.P0, low)[0] is True
    assert battery_allows(PriorityClass.P1, low)[0] is True
    assert battery_allows(PriorityClass.P2, low)[0] is False


def test_critical_battery_keeps_only_p0():
    critical = SyncContext(battery=0.05)
    assert battery_allows(PriorityClass.P0, critical)[0] is True
    assert battery_allows(PriorityClass.P1, critical)[0] is False
