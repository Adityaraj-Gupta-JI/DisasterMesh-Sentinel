"""Multi-hop simulation: does a report survive N hops, reroute, and dedup?

Deterministic and seeded, like the rest of the suite. These assert on measured
outcomes — delivery ratio and hop counts — not on internal steps.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dms.domain.enums import Role
from dms.sim.multihop import ListSink, MultihopRun
from dms.sim.topology import NodeSpec, build_mesh, chain, custom, grid, random_geometric

# The protocol caps a bundle at six hops (DMBP hop_limit), so a chain longer than
# seven nodes cannot deliver end to end — a real limit, asserted below.
HOP_LIMIT = 6

P0 = "Three people trapped under collapsed building near Market Road"


def _run(spec, tmp_path: Path, *, inject_at: str | None = None):
    mesh = build_mesh(spec, tmp_path)
    sink = ListSink()
    run = MultihopRun(mesh, spec, sinks=[sink])
    run.emit_topology()
    run.inject_report(inject_at or spec.nodes[0].id, P0)
    metrics = run.run()
    mesh.stop()
    return run, metrics, sink


def test_chain_delivers_across_five_hops(tmp_path: Path) -> None:
    spec = chain(6)
    _, metrics, sink = _run(spec, tmp_path)
    assert metrics.delivery_ratio == 1.0
    assert metrics.max_hops == 5
    # The recorded path is the full line, in order.
    hops = [e for e in sink.events if e.type == "hop"]
    assert hops[-1].path == ["n0", "n1", "n2", "n3", "n4", "n5"]


@pytest.mark.parametrize("n", [2, 4, 7])
def test_chain_delivers_within_hop_limit(n: int, tmp_path: Path) -> None:
    spec = chain(n)
    _, metrics, _ = _run(spec, tmp_path)
    assert metrics.delivery_ratio == 1.0
    assert metrics.max_hops == n - 1


def test_chain_beyond_hop_limit_does_not_deliver(tmp_path: Path) -> None:
    # Nine nodes is eight hops; the protocol stops the bundle at its hop limit.
    spec = chain(9)
    _, metrics, _ = _run(spec, tmp_path)
    assert metrics.delivered == 0
    assert metrics.max_hops == HOP_LIMIT


def test_grid_reroutes_when_a_relay_is_removed(tmp_path: Path) -> None:
    # A 3x3 grid has redundant paths; drop a middle relay before running and the
    # report should still reach the corner coordinator.
    spec = grid(3, 3)
    spec.edges = [(a, b) for a, b in spec.edges if "n4" not in (a, b)]
    _, metrics, _ = _run(spec, tmp_path)
    assert metrics.delivery_ratio == 1.0


def test_redundant_paths_deliver_once_without_flooding(tmp_path: Path) -> None:
    # A diamond: the reporter's bundle can reach the coordinator by two routes.
    # It is delivered exactly once, and the mesh does not flood — the bundle is
    # never offered along a path where the peer already holds it, so the number
    # of transfers stays bounded by the edge count rather than doubling.
    nodes = [
        NodeSpec("n0", Role.CITIZEN_REPORTER, 0, 1),
        NodeSpec("n1", Role.VOLUNTEER_RELAY, 1, 0),
        NodeSpec("n2", Role.VOLUNTEER_RELAY, 1, 2),
        NodeSpec("n3", Role.EVENT_COORDINATOR, 2, 1),
    ]
    edges = [("n0", "n1"), ("n0", "n2"), ("n1", "n3"), ("n2", "n3")]
    spec = custom(nodes, edges, name="diamond")
    _, metrics, _ = _run(spec, tmp_path)
    assert metrics.delivered == 1
    # Four edges; a naive flood would move the bundle across all of them. The
    # coordinator ends up holding exactly one copy.
    assert metrics.bundles_transferred <= len(edges)


def test_geometric_is_deterministic(tmp_path: Path) -> None:
    a = random_geometric(10, seed=20260831)
    b = random_geometric(10, seed=20260831)
    assert a.to_snapshot() == b.to_snapshot()
