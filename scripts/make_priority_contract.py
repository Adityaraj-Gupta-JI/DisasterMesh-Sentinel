#!/usr/bin/env python3
"""Generate the cross-language priority-engine contract.

The priority engine exists twice — Python in `protocol/dms/priority/engine.py` and
Kotlin in `android-app/.../domain/PriorityEngine.kt`. If they ever disagree, a phone and
the gateway would rank the same emergency differently. Mirrored unit tests do not
prevent that: two suites can drift together.

This writes a frozen contract of inputs and expected outputs, generated from the Python
reference. Both test suites read the same file, so drift on either side fails a test.

Regenerating is a deliberate act: the diff *is* the review. If a case's expected score
changes, that change must be justified, not absorbed.

    python3 scripts/make_priority_contract.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "protocol"))

from dms.domain.enums import ConditionType, DisasterType, Urgency  # noqa: E402
from dms.domain.models import Condition, Quantity  # noqa: E402
from dms.priority.engine import POLICY_VERSION, PriorityInputs, evaluate  # noqa: E402

OUTPUT = ROOT / "test-fixtures" / "priority-engine-contract.json"

#: Each case names the behaviour it pins down. Where a case exists because a real
#: mistake was possible, the note says which mistake.
CASES: list[dict] = [
    # --- urgency baseline ------------------------------------------------
    {"name": "urgency_critical_only", "urgency": "CRITICAL"},
    {"name": "urgency_high_only", "urgency": "HIGH"},
    {"name": "urgency_medium_only", "urgency": "MEDIUM"},
    {"name": "urgency_low_only", "urgency": "LOW"},
    {"name": "urgency_unknown_only", "urgency": "UNKNOWN"},
    # --- severity contribution -------------------------------------------
    {"name": "severity_zero", "urgency": "HIGH", "severity": 0},
    {"name": "severity_fifty", "urgency": "HIGH", "severity": 50},
    {"name": "severity_hundred", "urgency": "HIGH", "severity": 100},
    # --- hard escalation floors ------------------------------------------
    {
        "name": "life_threat_not_breathing_floors_p0",
        "note": "a 2% confident model must not be able to downgrade this",
        "urgency": "LOW",
        "severity": 5,
        "confidence": 0.02,
        "conditions": ["NOT_BREATHING"],
    },
    {
        "name": "life_threat_unconscious_floors_p0",
        "urgency": "LOW",
        "severity": 5,
        "confidence": 0.02,
        "conditions": ["UNCONSCIOUS"],
    },
    {
        "name": "trapped_without_hazard_floors_p1",
        "urgency": "MEDIUM",
        "severity": 30,
        "conditions": ["TRAPPED"],
    },
    {
        "name": "trapped_with_active_hazard_floors_p0",
        "urgency": "MEDIUM",
        "severity": 30,
        "conditions": ["TRAPPED"],
        "disaster_types": ["FIRE"],
    },
    {
        "name": "trapped_with_collapse_floors_p0",
        "urgency": "CRITICAL",
        "severity": 85,
        "confidence": 0.9,
        "disaster_types": ["BUILDING_COLLAPSE", "TRAPPED_PERSON"],
        "conditions": ["TRAPPED"],
        "people": {"value": 3, "raw": "Three people"},
    },
    {
        "name": "fire_with_known_people_floors_p1",
        "urgency": "LOW",
        "severity": 20,
        "disaster_types": ["FIRE"],
        "people": {"value": 2, "raw": "two"},
    },
    {
        "name": "fire_with_no_people_does_not_floor",
        "note": "a fire alone is not automatically a life threat",
        "urgency": "LOW",
        "severity": 20,
        "disaster_types": ["FIRE"],
    },
    # --- people counts ----------------------------------------------------
    {
        "name": "people_unknown_adds_nothing",
        "note": "unknown must never be treated as zero or guessed upward",
        "urgency": "HIGH",
        "severity": 50,
    },
    {"name": "people_one", "urgency": "HIGH", "severity": 50, "people": {"value": 1}},
    {"name": "people_three", "urgency": "HIGH", "severity": 50, "people": {"value": 3}},
    {
        "name": "people_large_count_is_capped",
        "note": "twenty people must not outrank a rule-triggered life threat",
        "urgency": "HIGH",
        "severity": 50,
        "people": {"value": 20},
    },
    {
        "name": "people_approximate_is_unknown",
        "urgency": "HIGH",
        "severity": 50,
        "people": {"value": None, "raw": "some people", "approximate": True},
    },
    # --- confidence and verification --------------------------------------
    {
        "name": "low_confidence_penalised_without_rule_trigger",
        "urgency": "HIGH",
        "severity": 50,
        "confidence": 0.1,
    },
    {
        "name": "low_confidence_not_penalised_when_rule_fired",
        "urgency": "HIGH",
        "severity": 50,
        "confidence": 0.1,
        "conditions": ["TRAPPED"],
    },
    {
        "name": "human_verified_bonus",
        "urgency": "HIGH",
        "severity": 50,
        "confidence": 0.9,
        "human_verified": True,
    },
    # --- age decay ---------------------------------------------------------
    {"name": "fresh_report", "urgency": "HIGH", "severity": 50, "age_seconds": 0},
    {"name": "one_hour_old_no_decay", "urgency": "HIGH", "severity": 50, "age_seconds": 3600},
    {"name": "six_hours_old_decays", "urgency": "HIGH", "severity": 50, "age_seconds": 21600},
    {
        "name": "very_old_decay_is_capped",
        "urgency": "HIGH",
        "severity": 50,
        "age_seconds": 864000,
    },
    # --- degraded mode ------------------------------------------------------
    {
        "name": "ai_unavailable_still_decides",
        "urgency": "HIGH",
        "severity": 50,
        "ai_available": False,
    },
    {
        "name": "ai_unavailable_life_threat_still_p0",
        "note": "the offline path must reach P0 without any model",
        "urgency": "UNKNOWN",
        "severity": 0,
        "confidence": 0.0,
        "ai_available": False,
        "conditions": ["NOT_BREATHING"],
    },
    # --- sensitivity --------------------------------------------------------
    {
        "name": "medical_disaster_type_is_medical",
        "urgency": "HIGH",
        "severity": 60,
        "disaster_types": ["MEDICAL"],
    },
    {
        "name": "condition_makes_it_medical",
        "urgency": "HIGH",
        "severity": 60,
        "conditions": ["BLEEDING"],
    },
    {
        "name": "flood_without_conditions_is_operational",
        "urgency": "HIGH",
        "severity": 60,
        "disaster_types": ["FLOOD"],
    },
    # --- class boundaries ---------------------------------------------------
    {"name": "boundary_p0_exact", "urgency": "CRITICAL", "severity": 100, "people": {"value": 3}},
    {"name": "boundary_p1_region", "urgency": "CRITICAL", "severity": 10},
    {"name": "boundary_p2_region", "urgency": "MEDIUM", "severity": 50},
    {"name": "boundary_p3_region", "urgency": "LOW", "severity": 10},
    {
        "name": "routine_logistics_is_p3",
        "urgency": "LOW",
        "severity": 12,
        "confidence": 0.8,
        "disaster_types": ["LOGISTICS"],
    },
]


def build_inputs(case: dict) -> PriorityInputs:
    people = case.get("people")
    quantity = (
        Quantity(
            value=people.get("value"),
            raw=people.get("raw"),
            approximate=people.get("approximate", False),
        )
        if people
        else Quantity.unknown()
    )
    return PriorityInputs(
        urgency=Urgency(case.get("urgency", "UNKNOWN")),
        severity=case.get("severity", 0),
        disaster_types=tuple(DisasterType(d) for d in case.get("disaster_types", [])),
        confidence=case.get("confidence", 0.0),
        people_affected=quantity,
        conditions=tuple(Condition(type=ConditionType(c)) for c in case.get("conditions", [])),
        hazards=tuple(case.get("hazards", [])),
        message_age_seconds=case.get("age_seconds", 0.0),
        human_verified=case.get("human_verified", False),
        ai_available=case.get("ai_available", True),
    )


def main() -> int:
    entries = []
    for case in CASES:
        decision = evaluate(build_inputs(case))
        entry = {
            "name": case["name"],
            "inputs": {
                "urgency": case.get("urgency", "UNKNOWN"),
                "severity": case.get("severity", 0),
                "disaster_types": case.get("disaster_types", []),
                "confidence": case.get("confidence", 0.0),
                "people": case.get("people"),
                "conditions": case.get("conditions", []),
                "hazards": case.get("hazards", []),
                "age_seconds": case.get("age_seconds", 0.0),
                "human_verified": case.get("human_verified", False),
                "ai_available": case.get("ai_available", True),
            },
            # Values only. Explanation prose differs between languages by design;
            # what must not differ is the decision.
            "expected": {
                "score": decision.score,
                "priority_class": decision.priority_class.value,
                "ttl_seconds": decision.ttl_seconds,
                "replication_limit": decision.replication_limit,
                "sensitivity": decision.sensitivity.value,
                "requires_ack": decision.requires_ack,
                "text_before_media": decision.text_before_media,
                "escalated_by_rule": decision.escalated_by_rule,
            },
        }
        if "note" in case:
            entry["note"] = case["note"]
        entries.append(entry)

    contract = {
        "$comment": (
            "Frozen cross-language contract for the priority engine. Generated by "
            "scripts/make_priority_contract.py from the Python reference. Read by "
            "protocol/tests/test_priority_contract.py and by the Android "
            "PriorityContractTest. Regenerate deliberately; the diff is the review."
        ),
        "policy_version": POLICY_VERSION,
        "generated_from": "protocol/dms/priority/engine.py",
        "case_count": len(entries),
        "cases": entries,
    }
    OUTPUT.write_text(json.dumps(contract, indent=2) + "\n")

    by_class: dict[str, int] = {}
    for entry in entries:
        cls = entry["expected"]["priority_class"]
        by_class[cls] = by_class.get(cls, 0) + 1
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    print(f"  {len(entries)} cases · policy {POLICY_VERSION}")
    print(f"  coverage by class: {dict(sorted(by_class.items()))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
