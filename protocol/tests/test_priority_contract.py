"""Conformance against the frozen cross-language priority contract.

The priority engine exists twice — here and in Kotlin. Mirrored unit tests do not stop
the two drifting apart, because two suites can be edited together. A single frozen file
of inputs and expected outputs can not: whichever side changes, its test fails.

Regenerate with `python3 scripts/make_priority_contract.py`. The diff is the review.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from dms.domain.enums import ConditionType, DisasterType, Urgency
from dms.domain.models import Condition, Quantity
from dms.priority.engine import POLICY_VERSION, PriorityInputs, evaluate

CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "test-fixtures" / "priority-engine-contract.json"
)


@pytest.fixture(scope="module")
def contract() -> dict:
    assert CONTRACT_PATH.exists(), (
        f"{CONTRACT_PATH} is missing — run scripts/make_priority_contract.py"
    )
    return json.loads(CONTRACT_PATH.read_text())


def build_inputs(spec: dict) -> PriorityInputs:
    people = spec.get("people")
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
        urgency=Urgency(spec["urgency"]),
        severity=spec["severity"],
        disaster_types=tuple(DisasterType(d) for d in spec["disaster_types"]),
        confidence=spec["confidence"],
        people_affected=quantity,
        conditions=tuple(Condition(type=ConditionType(c)) for c in spec["conditions"]),
        hazards=tuple(spec["hazards"]),
        message_age_seconds=spec["age_seconds"],
        human_verified=spec["human_verified"],
        ai_available=spec["ai_available"],
    )


def load_cases() -> list[tuple[str, dict]]:
    if not CONTRACT_PATH.exists():  # pragma: no cover - guarded by the fixture too
        return []
    data = json.loads(CONTRACT_PATH.read_text())
    return [(case["name"], case) for case in data["cases"]]


def test_contract_exists_and_is_current(contract):
    assert contract["policy_version"] == POLICY_VERSION, (
        "the contract was generated under a different policy version; regenerate it "
        "deliberately and review the diff"
    )
    assert contract["case_count"] == len(contract["cases"])
    assert contract["case_count"] >= 30, "the contract must cover the decision surface"


@pytest.mark.parametrize(
    "name,case", load_cases(), ids=lambda value: value if isinstance(value, str) else ""
)
def test_python_engine_matches_the_contract(name, case):
    decision = evaluate(build_inputs(case["inputs"]))
    expected = case["expected"]
    actual = {
        "score": decision.score,
        "priority_class": decision.priority_class.value,
        "ttl_seconds": decision.ttl_seconds,
        "replication_limit": decision.replication_limit,
        "sensitivity": decision.sensitivity.value,
        "requires_ack": decision.requires_ack,
        "text_before_media": decision.text_before_media,
        "escalated_by_rule": decision.escalated_by_rule,
    }
    assert actual == expected, (
        f"case '{name}' drifted from the contract.\n"
        f"  note: {case.get('note', '—')}\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}\n"
        "If this change is intended, regenerate the contract and justify the diff."
    )


def test_every_case_is_covered_by_the_contract(contract):
    """A contract with duplicate or missing names silently loses coverage."""
    names = [case["name"] for case in contract["cases"]]
    assert len(names) == len(set(names)), "duplicate case names in the contract"


def test_life_threat_cases_are_present_and_p0(contract):
    """The property that matters most must be pinned, not merely present."""
    life_threat = [
        case
        for case in contract["cases"]
        if {"NOT_BREATHING", "UNCONSCIOUS"} & set(case["inputs"]["conditions"])
    ]
    assert len(life_threat) >= 3, "the contract must pin the life-threat floor"
    for case in life_threat:
        assert case["expected"]["priority_class"] == "P0", case["name"]
        assert case["expected"]["escalated_by_rule"] is True, case["name"]


def test_unknown_people_never_scores_above_a_known_count(contract):
    unknown = next(c for c in contract["cases"] if c["name"] == "people_unknown_adds_nothing")
    known = next(c for c in contract["cases"] if c["name"] == "people_three")
    assert unknown["expected"]["score"] < known["expected"]["score"]
