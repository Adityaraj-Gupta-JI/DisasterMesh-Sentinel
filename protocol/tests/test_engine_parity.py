"""Structural parity between the Python and Kotlin priority engines.

The full behavioural contract lives in `test-fixtures/priority-engine-contract.json` and
is checked on both sides — but the Kotlin side cannot be executed here (no Android SDK),
so that half of the guarantee is currently unenforced.

This module closes the gap in the meantime by reading the Kotlin *source* and comparing
its rule tables and coefficients against the Python ones.

What this proves: the two engines encode the same numbers, thresholds, and escalation
rules. What it does not prove: that the Kotlin control flow combines them identically —
only compiling and running `PriorityContractTest` proves that. It is a smoke alarm, not
a fire door, and it is here because a silent disagreement about how urgent an emergency
is would be worse than an obvious one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from dms.priority import engine as py_engine

KOTLIN_PATH = (
    Path(__file__).resolve().parents[2]
    / "android-app/app/src/main/java/org/disastermesh/sentinel/domain/PriorityEngine.kt"
)


@pytest.fixture(scope="module")
def kotlin_source() -> str:
    if not KOTLIN_PATH.exists():
        pytest.skip(f"Kotlin engine not present at {KOTLIN_PATH}")
    return KOTLIN_PATH.read_text(encoding="utf-8")


def kotlin_map(source: str, name: str) -> dict[str, int]:
    """Extract a `private val NAME = mapOf(A.B to 1, ...)` table."""
    match = re.search(rf"val {name} = mapOf\((.*?)\n    \)", source, re.DOTALL)
    assert match, f"could not find {name} in the Kotlin engine"
    body = match.group(1)
    out: dict[str, int] = {}
    for enum_key, value_expr in re.findall(r"\w+\.(\w+) to ([0-9]+(?:\s*\*\s*[0-9]+)?)L?", body):
        # The expression is digits and '*' taken from our own source file; Kotlin
        # writes durations as `6 * 3600L`, so it has to be evaluated to compare.
        out[enum_key] = eval(value_expr, {"__builtins__": {}})  # noqa: S307
    return out


def test_urgency_base_tables_match(kotlin_source):
    kotlin = kotlin_map(kotlin_source, "URGENCY_BASE")
    python = {urgency.value: score for urgency, score in py_engine.URGENCY_BASE.items()}
    assert kotlin == python, "the two engines disagree on the urgency baseline"


def test_ttl_tables_match(kotlin_source):
    kotlin = kotlin_map(kotlin_source, "TTL_SECONDS")
    python = {cls.value: seconds for cls, seconds in py_engine.TTL_SECONDS.items()}
    assert kotlin == python, "the two engines disagree on how long a bundle lives"


def test_replication_tables_match(kotlin_source):
    kotlin = kotlin_map(kotlin_source, "REPLICATION_LIMIT")
    python = {cls.value: limit for cls, limit in py_engine.REPLICATION_LIMIT.items()}
    assert kotlin == python, "the two engines disagree on how widely a bundle spreads"


def test_class_thresholds_match(kotlin_source):
    """P0/P1/P2 boundaries decide who gets help first; they must be identical."""
    found = re.findall(r"score >= (\d+) -> PriorityClass\.(P\d)", kotlin_source)
    kotlin = [(int(score), cls) for score, cls in found]
    python = [(score, cls.value) for score, cls in py_engine.CLASS_THRESHOLDS]
    assert kotlin == python, f"class thresholds differ: kotlin={kotlin} python={python}"


def test_life_threat_conditions_match(kotlin_source):
    match = re.search(r"LIFE_THREAT = setOf\((.*?)\)", kotlin_source, re.DOTALL)
    assert match, "LIFE_THREAT set not found in the Kotlin engine"
    kotlin = {name for name in re.findall(r"ConditionType\.(\w+)", match.group(1))}
    python = {condition.value for condition in py_engine.LIFE_THREAT_CONDITIONS}
    assert kotlin == python, "the two engines disagree on what counts as a life threat"


def test_active_hazard_types_match(kotlin_source):
    match = re.search(r"ACTIVE_HAZARDS = setOf\((.*?)\)", kotlin_source, re.DOTALL)
    assert match, "ACTIVE_HAZARDS set not found in the Kotlin engine"
    kotlin = {name for name in re.findall(r"DisasterType\.(\w+)", match.group(1))}
    python = {disaster.value for disaster in py_engine.ACTIVE_HAZARD_TYPES}
    assert kotlin == python, "the two engines disagree on what an active hazard is"


def test_escalation_rule_messages_match(kotlin_source):
    """The RULE lines are the human-readable form of the floors.

    Comparing them catches a floor that was changed on one side only, because the
    number is inside the message.
    """
    kotlin = set(re.findall(r'"(RULE: [^"]+)"', kotlin_source))
    python_source = Path(py_engine.__file__).read_text(encoding="utf-8")
    python = set(re.findall(r'"(RULE: [^"]+)"', python_source))
    assert kotlin == python, (
        "escalation rules differ between the engines:\n"
        f"  only in Kotlin: {sorted(kotlin - python)}\n"
        f"  only in Python: {sorted(python - kotlin)}"
    )


@pytest.mark.parametrize(
    "description,python_pattern,kotlin_pattern",
    [
        (
            "severity multiplier",
            r"inputs\.severity \* (0\.\d+)",
            r"inputs\.severity \* (0\.\d+)",
        ),
        ("people cap", r"min\((\d+), \(people\.value", r"minOf\((\d+), \(people\.value"),
        (
            "people multiplier",
            r"people\.value or 0\) \* (\d+)",
            r"people\.value \?: 0\) \* (\d+)",
        ),
        ("human verified bonus", r"human verified → \+(\d+)", r"human verified → \+(\d+)"),
        (
            "low confidence penalty",
            r"no rule trigger → -(\d+)",
            r"no rule trigger → -(\d+)",
        ),
        ("age decay threshold", r"if age_minutes > (\d+)", r"if \(ageMinutes > (\d+)\)"),
        ("age decay divisor", r"age_minutes - 60\) // (\d+)", r"ageMinutes - 60\) / (\d+)"),
        ("age decay cap", r"decay = min\((\d+),", r"decay = minOf\((\d+),"),
    ],
)
def test_scoring_coefficients_match(kotlin_source, description, python_pattern, kotlin_pattern):
    python_source = Path(py_engine.__file__).read_text(encoding="utf-8")
    python_match = re.search(python_pattern, python_source)
    kotlin_match = re.search(kotlin_pattern, kotlin_source)
    assert python_match, f"could not locate the {description} in the Python engine"
    assert kotlin_match, f"could not locate the {description} in the Kotlin engine"
    assert python_match.group(1) == kotlin_match.group(1), (
        f"{description} differs: python={python_match.group(1)} kotlin={kotlin_match.group(1)}"
    )


def test_policy_versions_match(kotlin_source):
    kotlin = re.search(r'POLICY_VERSION = "([^"]+)"', kotlin_source)
    assert kotlin, "POLICY_VERSION not found in the Kotlin engine"
    assert kotlin.group(1) == py_engine.POLICY_VERSION, (
        "policy versions differ; a decision made on a phone could not be compared "
        "with one made on the gateway"
    )


def test_kotlin_contract_test_exists():
    """The Kotlin side of the contract must exist even though it cannot run here."""
    # PriorityEngine.kt sits at src/main/java/org/disastermesh/sentinel/domain/,
    # so parents[6] is `src` and the test tree hangs off it.
    path = KOTLIN_PATH.parents[6] / "test/java/org/disastermesh/sentinel/PriorityContractTest.kt"
    assert path.exists(), (
        "the Kotlin conformance test is missing; the contract would then be enforced "
        "on one side only"
    )
    source = path.read_text(encoding="utf-8")
    assert "priority-engine-contract.json" in source, (
        "the Kotlin test must read the same frozen contract, not its own copy"
    )
