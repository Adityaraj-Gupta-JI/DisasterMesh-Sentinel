"""Gateway mesh endpoints: run registry, event cursor, and background simulate.

The mesh view is in-memory and ephemeral; these check the parts the dashboard
depends on — creating a run, streaming events, and paging with a ``since`` cursor.
"""

from __future__ import annotations

import time

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
AUTH = {"Authorization": "Bearer dev-coordinator-key"}


def test_create_run_and_stream_events() -> None:
    topology = {"name": "chain-3", "nodes": [{"id": "n0", "role": "CITIZEN_REPORTER", "x": 0, "y": 0}], "edges": []}
    run_id = client.post("/v1/mesh/runs", json={"topology": topology}, headers=AUTH).json()["run_id"]
    assert run_id

    batch = [
        {"seq": 0, "type": "bundle_injected", "to_node": "n0"},
        {"seq": 1, "type": "hop", "from_node": "n0", "to_node": "n1", "hop": 1},
    ]
    r = client.post(f"/v1/mesh/runs/{run_id}/events", json={"events": batch}, headers=AUTH)
    assert r.json()["ok"] is True

    events = client.get(f"/v1/mesh/runs/{run_id}/events?since=-1", headers=AUTH).json()
    assert len(events["events"]) == 2
    assert events["events"][0]["type"] == "bundle_injected"


def test_since_cursor_returns_only_new_events() -> None:
    run_id = client.post("/v1/mesh/runs", json={"topology": {"nodes": [], "edges": []}}, headers=AUTH).json()["run_id"]
    client.post(f"/v1/mesh/runs/{run_id}/events", json={"events": [{"type": "hop"}, {"type": "hop"}]}, headers=AUTH)
    first = client.get(f"/v1/mesh/runs/{run_id}/events?since=-1", headers=AUTH).json()
    latest = first["latest_seq"]
    client.post(f"/v1/mesh/runs/{run_id}/events", json={"events": [{"type": "delivered"}]}, headers=AUTH)
    delta = client.get(f"/v1/mesh/runs/{run_id}/events?since={latest}", headers=AUTH).json()
    assert [e["type"] for e in delta["events"]] == ["delivered"]


def test_unknown_run_is_404() -> None:
    assert client.get("/v1/mesh/runs/run_nope/events", headers=AUTH).status_code == 404


def test_simulate_runs_and_delivers() -> None:
    run_id = client.post(
        "/v1/mesh/simulate",
        json={"topology": "chain", "nodes": 4, "step_delay": 0.0},
        headers=AUTH,
    ).json()["run_id"]

    # The run is backgrounded; poll briefly for completion.
    for _ in range(50):
        summary = client.get("/v1/mesh/runs/latest", headers=AUTH).json()
        if summary.get("run_id") == run_id and summary.get("done"):
            break
        time.sleep(0.05)
    events = client.get(f"/v1/mesh/runs/{run_id}/events?since=-1", headers=AUTH).json()
    assert events["done"] is True
    assert any(e["type"] == "delivered" for e in events["events"])
    assert events["metrics"]["delivery_ratio"] == 1.0
