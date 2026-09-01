"""The simulator is itself under test: each scenario must meet its bar."""

from __future__ import annotations

import json

import pytest
from dms.sim.simulator import SCENARIOS, run_all, write_reports


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    return run_all(tmp_path_factory.mktemp("sim"))


def by_name(results, prefix):
    return next(r for r in results if r.name.startswith(prefix))


def test_all_ten_scenarios_run(results):
    assert len(results) == len(SCENARIOS) == 10


def test_critical_relay_delivers_and_acknowledges(results):
    r = by_name(results, "1_")
    assert r.delivery_ratio == 1.0
    assert r.p0_delivery_seconds is not None
    assert r.acknowledgement_latency_seconds is not None
    assert "relay could read payloads: False" in r.notes


def test_intermittent_contact_loses_nothing(results):
    assert by_name(results, "2_").delivery_ratio == 1.0


def test_large_routine_file_never_delays_critical_text(results):
    r = by_name(results, "3_")
    assert r.delivery_ratio == 1.0
    assert "P0 text preceded bulk media: True" in r.notes


def test_late_gateway_still_receives(results):
    assert by_name(results, "4_").delivery_ratio == 1.0


def test_duplicate_reports_are_clustered_provisionally(results):
    r = by_name(results, "5_")
    assert r.duplicate_bundles_suppressed >= 1
    assert any("human_reviewed=False" in n for n in r.notes)


def test_unauthorized_nodes_are_refused(results):
    assert by_name(results, "6_").unauthorized_rejections >= 2


def test_low_battery_keeps_p0_and_sheds_p3(results):
    r = by_name(results, "7_")
    assert "P0 delivered at 5% battery: True" in r.notes
    assert "P3 deferred at 5% battery: True" in r.notes


def test_interrupted_file_resumes_and_verifies(results):
    r = by_name(results, "8_")
    assert r.file_completion_ratio == 1.0
    assert any("digest verified" in n for n in r.notes)


def test_ai_outage_still_produces_p0(results):
    r = by_name(results, "9_")
    assert "priority without AI: P0" in r.notes
    assert "original text preserved: True" in r.notes


def test_conflicting_counts_are_surfaced_not_averaged(results):
    r = by_name(results, "10_")
    assert any("disagree" in n for n in r.notes)


def test_reports_are_written_as_json_and_csv(results, tmp_path):
    json_path, csv_path = write_reports(results, tmp_path)
    payload = json.loads(json_path.read_text())
    assert payload["seed"] and len(payload["scenarios"]) == 10
    assert "delivery_ratio" in csv_path.read_text().splitlines()[0]


def test_simulation_is_deterministic(tmp_path_factory):
    first = run_all(tmp_path_factory.mktemp("a"))
    second = run_all(tmp_path_factory.mktemp("b"))
    assert [r.delivered for r in first] == [r.delivered for r in second]
    assert [r.bundles_transferred for r in first] == [r.bundles_transferred for r in second]
