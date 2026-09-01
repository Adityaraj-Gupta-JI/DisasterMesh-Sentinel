"""Live multi-hop mesh view for the coordinator dashboard.

The mesh is ephemeral by design, and so is this: runs live in memory, in a bounded
ring buffer per run, and vanish on restart. The gateway does not own the mesh — it
only mirrors what a simulation (or, later, real nodes) reports, so the dashboard can
watch a report hop from node to node in near real time.

Two ways to feed it:
  * an external process streams events in over ``POST /runs`` + ``/events`` (the CLI);
  * the dashboard asks the gateway itself to run a scenario in the background.
Both end up in the same store, and the dashboard polls ``/events?since=`` for the rest.
"""

from __future__ import annotations

import threading
from collections import deque
from datetime import UTC, datetime
from typing import Any

from dms.domain.enums import Role
from dms.domain.models import new_id
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from .security import Principal, current_principal

router = APIRouter(prefix="/v1/mesh", tags=["mesh"])


def _optional_principal(authorization: str | None = Header(default=None)) -> Principal:
    """Same lenient auth the demo uses elsewhere: a bearer token if present,
    otherwise the demo coordinator. Mirrors main._optional_principal without the
    import cycle (main includes this router)."""
    if authorization and authorization.lower().startswith("bearer "):
        try:
            return current_principal(authorization)
        except Exception:
            pass
    return Principal(user_id="demo_user", role=Role.EVENT_COORDINATOR, organization_id="org_demo")

MAX_EVENTS = 5000


class MeshRun:
    """One simulation run: its graph, an ordered ring of events, and a summary."""

    def __init__(self, run_id: str, topology: dict, organization_id: str) -> None:
        self.run_id = run_id
        self.topology = topology
        self.organization_id = organization_id
        self.events: deque[dict] = deque(maxlen=MAX_EVENTS)
        self.metrics: dict[str, Any] = {}
        self.done = False
        self.created_at = datetime.now(UTC).isoformat()
        self._lock = threading.Lock()
        self._next_seq = 0

    def append(self, events: list[dict]) -> int:
        """Append a batch, stamping a monotonic seq the dashboard can page on."""
        with self._lock:
            for event in events:
                event = dict(event)
                event["seq"] = self._next_seq
                self._next_seq += 1
                self.events.append(event)
            return self._next_seq

    def since(self, seq: int) -> list[dict]:
        with self._lock:
            return [e for e in self.events if e["seq"] > seq]

    @property
    def latest_seq(self) -> int:
        return self._next_seq - 1

    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "topology": self.topology,
            "metrics": self.metrics,
            "done": self.done,
            "created_at": self.created_at,
            "latest_seq": self.latest_seq,
            "event_count": len(self.events),
        }


class MeshRunStore:
    """All runs, newest wins for ``latest``. Purely in-memory."""

    def __init__(self) -> None:
        self.runs: dict[str, MeshRun] = {}
        self.order: list[str] = []

    def create(self, topology: dict, organization_id: str) -> MeshRun:
        run_id = new_id("run")
        run = MeshRun(run_id, topology, organization_id)
        self.runs[run_id] = run
        self.order.append(run_id)
        # Keep memory bounded: forget the oldest runs.
        while len(self.order) > 20:
            self.runs.pop(self.order.pop(0), None)
        return run

    def get(self, run_id: str) -> MeshRun:
        run = self.runs.get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail={"error": "unknown_run"})
        return run

    def latest(self) -> MeshRun | None:
        return self.runs.get(self.order[-1]) if self.order else None


STORE = MeshRunStore()


# ------------------------------------------------------------------- ingestion


@router.post("/runs")
def create_run(
    body: dict = Body(...),
    principal: Principal = Depends(_optional_principal),
) -> dict:
    """Register a run from its topology snapshot; returns the run_id to stream to."""
    topology = body.get("topology") or {}
    run = STORE.create(topology, principal.organization_id)
    return {"run_id": run.run_id}


@router.post("/runs/{run_id}/events")
def append_events(
    run_id: str,
    body: dict = Body(...),
    principal: Principal = Depends(_optional_principal),
) -> dict:
    """Append a batch of mesh events. This is what an external sink calls."""
    run = STORE.get(run_id)
    events = body.get("events") or []
    latest = run.append(events)
    if body.get("metrics"):
        run.metrics = body["metrics"]
    if body.get("done"):
        run.done = True
    return {"ok": True, "latest_seq": latest - 1}


# --------------------------------------------------------------------- reading


@router.get("/runs/latest")
def latest_run(principal: Principal = Depends(_optional_principal)) -> dict:
    run = STORE.latest()
    if run is None:
        return {"run_id": None}
    return run.summary()


@router.get("/runs/{run_id}/events")
def run_events(
    run_id: str,
    since: int = Query(default=-1),
    principal: Principal = Depends(_optional_principal),
) -> dict:
    """Events with seq > ``since`` — the dashboard's incremental cursor."""
    run = STORE.get(run_id)
    return {
        "events": run.since(since),
        "latest_seq": run.latest_seq,
        "done": run.done,
        "metrics": run.metrics,
    }


# ------------------------------------------------------------ dashboard trigger


@router.post("/simulate")
def simulate(
    body: dict = Body(default={}),
    principal: Principal = Depends(_optional_principal),
) -> dict:
    """Run a scenario in the background, streaming into a fresh run.

    Lets the dashboard start a live multi-hop run with no terminal. The heavy
    lifting stays in the simulator; here we just wire its event stream into the
    store and pace it so hops are watchable.
    """
    from dms.sim import topology as topo
    from dms.sim.multihop import MultihopRun

    kind = body.get("topology", "chain")
    nodes = int(body.get("nodes", 6))
    seed = int(body.get("seed", 20260831))
    step_delay = float(body.get("step_delay", 0.4))
    text = body.get("text", "Three people trapped under collapsed building near Market Road")

    if kind == "chain":
        spec = topo.chain(nodes)
    elif kind == "grid":
        w = int(body.get("width", 3))
        h = int(body.get("height", 3))
        spec = topo.grid(w, h)
    elif kind == "geometric":
        spec = topo.random_geometric(nodes, radius=float(body.get("radius", 0.4)), seed=seed)
    else:
        raise HTTPException(status_code=400, detail={"error": "unknown_topology"})

    run = STORE.create(spec.to_snapshot(), principal.organization_id)

    def sink(event) -> None:
        run.append([event.to_dict()])

    def worker() -> None:
        import tempfile
        from pathlib import Path

        tmp = Path(tempfile.mkdtemp(prefix="mesh_run_"))
        mesh = topo.build_mesh(spec, tmp)
        try:
            mrun = MultihopRun(mesh, spec, sinks=[sink], step_delay=step_delay)
            mrun.emit_topology()
            mrun.inject_report(spec.nodes[0].id, text)
            metrics = mrun.run()
            run.metrics = metrics.to_dict()
        finally:
            run.done = True
            try:
                mesh.stop()
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()
    return {"run_id": run.run_id}
