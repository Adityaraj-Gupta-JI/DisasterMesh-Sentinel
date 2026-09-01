"""General mesh topologies for multi-hop simulation.

The demo harness wires one fixed line — reporter, relay, coordinator. Multi-hop
simulation needs arbitrary graphs: long chains, grids, and random scatter that
looks like phones dropped across a disaster zone. This module builds those, on
top of the same :class:`Mesh`, :class:`MockRadio`, and node stack the tests use,
so nothing here re-implements the protocol — it only decides who can reach whom.

Every node gets a 2-D position so a dashboard can lay the graph out without
guessing. Positions are cosmetic for chain and grid, and load-bearing for the
random geometric graph, where they decide which nodes are in range.
"""

from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass, field
from pathlib import Path

from ..domain.clock import FixedClock
from ..domain.enums import Role
from ..node import NodeConfig
from ..transport.mock import MockRadio
from .harness import Mesh


@dataclass
class NodeSpec:
    """One node in a topology: its id, role, and where it sits on the canvas."""

    id: str
    role: Role
    x: float = 0.0
    y: float = 0.0


@dataclass
class TopologySpec:
    """A declarative description of a mesh: nodes, positions, and who is in range."""

    name: str
    nodes: list[NodeSpec] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def to_snapshot(self) -> dict:
        """A JSON-ready picture of the graph, for the event stream and dashboard."""
        return {
            "name": self.name,
            "nodes": [
                {"id": n.id, "role": n.role.value, "x": round(n.x, 4), "y": round(n.y, 4)}
                for n in self.nodes
            ],
            "edges": [{"a": a, "b": b} for a, b in self.edges],
        }


def build_mesh(spec: TopologySpec, data_dir: Path, *, relays_hold_key: bool = False) -> Mesh:
    """Realise a :class:`TopologySpec` as a live mesh.

    Endpoints (reporters and coordinators) get the organization key so they can
    read what they send and receive. Relays deliberately do not: they carry
    ciphertext and routing metadata across hops without reading it — unless
    ``relays_hold_key`` is set for a scenario that needs it.
    """
    org_key = os.urandom(32)
    mesh = Mesh(radio=MockRadio(), clock=FixedClock())
    for node in spec.nodes:
        holds_key = node.role is not Role.VOLUNTEER_RELAY or relays_hold_key
        mesh.add(
            node.id,
            node.role,
            data_dir=data_dir,
            org_key=org_key if holds_key else None,
            config=NodeConfig(),
        )
    mesh.trust_all()
    for a, b in spec.edges:
        mesh.connect(a, b)
    # Record the layout on the mesh so the driver can emit it without re-deriving.
    mesh.topology = spec  # type: ignore[attr-defined]
    return mesh


# --------------------------------------------------------------------- builders


def chain(n: int, *, name: str | None = None) -> TopologySpec:
    """A straight line: reporter → relay → … → coordinator.

    The purest multi-hop case. Node 0 reports, node n-1 coordinates, everything
    between is a relay. A report must survive n-1 hops to arrive.
    """
    if n < 2:
        raise ValueError("a chain needs at least 2 nodes")
    nodes = []
    for i in range(n):
        if i == 0:
            role = Role.CITIZEN_REPORTER
        elif i == n - 1:
            role = Role.EVENT_COORDINATOR
        else:
            role = Role.VOLUNTEER_RELAY
        nodes.append(NodeSpec(id=f"n{i}", role=role, x=float(i), y=0.0))
    edges = [(f"n{i}", f"n{i + 1}") for i in range(n - 1)]
    return TopologySpec(name=name or f"chain-{n}", nodes=nodes, edges=edges)


def grid(w: int, h: int, *, name: str | None = None) -> TopologySpec:
    """A w×h grid where each node reaches its 4 orthogonal neighbours.

    Redundant paths exist, so a scenario can kill one relay and watch a report
    reroute. The top-left corner reports; the bottom-right coordinates.
    """
    if w < 1 or h < 1 or w * h < 2:
        raise ValueError("a grid needs at least 2 nodes")

    def nid(cx: int, cy: int) -> str:
        return f"n{cy * w + cx}"

    nodes = []
    for cy in range(h):
        for cx in range(w):
            if cx == 0 and cy == 0:
                role = Role.CITIZEN_REPORTER
            elif cx == w - 1 and cy == h - 1:
                role = Role.EVENT_COORDINATOR
            else:
                role = Role.VOLUNTEER_RELAY
            nodes.append(NodeSpec(id=nid(cx, cy), role=role, x=float(cx), y=float(cy)))
    edges = []
    for cy in range(h):
        for cx in range(w):
            if cx + 1 < w:
                edges.append((nid(cx, cy), nid(cx + 1, cy)))
            if cy + 1 < h:
                edges.append((nid(cx, cy), nid(cx, cy + 1)))
    return TopologySpec(name=name or f"grid-{w}x{h}", nodes=nodes, edges=edges)


def random_geometric(
    n: int, *, radius: float = 0.35, seed: int = 20260831, name: str | None = None
) -> TopologySpec:
    """n nodes scattered on the unit square, linked when within ``radius``.

    The most realistic disaster layout: phones fall where people are, and two
    can talk only if they are close enough. Node 0 reports; the node furthest
    from it becomes the coordinator, so a report has real distance to cross.
    A given seed always yields the same map.
    """
    if n < 2:
        raise ValueError("need at least 2 nodes")
    rng = random.Random(seed)
    pos = [(rng.random(), rng.random()) for _ in range(n)]
    # Coordinator = node furthest from the reporter, so hops are unavoidable.
    ox, oy = pos[0]
    coord = max(range(1, n), key=lambda i: math.dist((ox, oy), pos[i]))
    nodes = []
    for i in range(n):
        if i == 0:
            role = Role.CITIZEN_REPORTER
        elif i == coord:
            role = Role.EVENT_COORDINATOR
        else:
            role = Role.VOLUNTEER_RELAY
        nodes.append(NodeSpec(id=f"n{i}", role=role, x=pos[i][0], y=pos[i][1]))
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if math.dist(pos[i], pos[j]) <= radius:
                edges.append((f"n{i}", f"n{j}"))
    return TopologySpec(name=name or f"geometric-{n}", nodes=nodes, edges=edges)


def custom(nodes: list[NodeSpec], edges: list[tuple[str, str]], *, name: str = "custom") -> TopologySpec:
    """A hand-drawn topology. Positions default to origin if you don't care."""
    return TopologySpec(name=name, nodes=list(nodes), edges=list(edges))
