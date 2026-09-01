"""Multi-hop epidemic driver and its event stream.

The demo harness syncs one pair of nodes. A real mesh gossips: every node offers
what it carries to every neighbour in range, round after round, until nothing new
moves. That is store-carry-forward routing — no routing tables, just "show me
what you have." This module runs that gossip over any :mod:`topology`, and — the
part everything else depends on — emits an ordered stream of :class:`MeshEvent`
as it goes. The terminal view, the backend, and the dashboard are all just
renderers of that one stream.

Hops are not inferred here: the protocol already stamps every bundle with a
``hop_count`` and a ``path``. The driver wraps :meth:`MeshNode.accept_bundle`
to read those out the moment a bundle lands, and turns each landing into an event.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from itertools import count

from ..domain.enums import Role
from .harness import Mesh
from .topology import TopologySpec

Sink = Callable[["MeshEvent"], None]


@dataclass
class MeshEvent:
    """One thing that happened in the mesh, in order. The whole contract."""

    seq: int
    round: int
    type: str  # node_added|link_up|link_down|bundle_injected|hop|delivered|
    #            duplicate_suppressed|quiescent
    from_node: str | None = None
    to_node: str | None = None
    bundle_id: str | None = None
    incident_id: str | None = None
    hop: int | None = None
    path: list[str] = field(default_factory=list)
    ts: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class ListSink:
    """Collects events into a list — for tests, the CLI, and the terminal view."""

    def __init__(self) -> None:
        self.events: list[MeshEvent] = []

    def __call__(self, event: MeshEvent) -> None:
        self.events.append(event)


@dataclass
class MeshMetrics:
    """What a run measured. Plain numbers; the caller decides if they are good."""

    delivered: int = 0
    expected: int = 0
    avg_hops: float = 0.0
    max_hops: int = 0
    bundles_transferred: int = 0
    duplicates_suppressed: int = 0
    rounds: int = 0

    @property
    def delivery_ratio(self) -> float:
        return self.delivered / self.expected if self.expected else 0.0

    def to_dict(self) -> dict:
        return asdict(self) | {"delivery_ratio": round(self.delivery_ratio, 4)}


class MultihopRun:
    """Drives epidemic gossip over a mesh and streams what happens.

    Construct it with a built mesh, register one or more sinks, inject reports,
    then :meth:`run`. Metrics are available on :attr:`metrics` afterwards.
    """

    def __init__(
        self,
        mesh: Mesh,
        topology: TopologySpec,
        *,
        sinks: list[Sink] | None = None,
        step_delay: float = 0.0,
    ) -> None:
        self.mesh = mesh
        self.topology = topology
        self.sinks = sinks or []
        self.step_delay = step_delay
        self.metrics = MeshMetrics()
        self._seq = count()
        self._round = 0
        self._delivered_incidents: set[str] = set()
        self._hop_counts: list[int] = []
        self._coordinators = [
            n.id for n in topology.nodes if n.role is Role.EVENT_COORDINATOR
        ]
        self._instrument()

    # ------------------------------------------------------------------- events

    def _emit(self, type_: str, **kw) -> None:
        event = MeshEvent(seq=next(self._seq), round=self._round, type=type_, ts=time.time(), **kw)
        for sink in self.sinks:
            sink(event)
        if self.step_delay and type_ in {"hop", "delivered", "bundle_injected"}:
            time.sleep(self.step_delay)

    def emit_topology(self) -> None:
        """Emit the initial graph so a renderer can lay out before any hop."""
        for node in self.topology.nodes:
            self._emit("node_added", to_node=node.id)
        for a, b in self.topology.edges:
            self._emit("link_up", from_node=a, to_node=b)

    # -------------------------------------------------------------- instrument

    def _instrument(self) -> None:
        """Wrap every node's accept_bundle so each landing becomes an event."""
        for node in self.mesh.nodes.values():
            original = node.accept_bundle
            node_id = node.identity.id

            def wrapped(bundle, *, received_from, _orig=original, _self=self, _to=node_id):
                stored, reason = _orig(bundle, received_from=received_from)
                if reason == "duplicate":
                    _self.metrics.duplicates_suppressed += 1
                    _self._emit(
                        "duplicate_suppressed",
                        from_node=received_from,
                        to_node=_to,
                        bundle_id=bundle.id,
                        incident_id=bundle.header.incident_id,
                    )
                    return stored, reason
                if stored:
                    _self.metrics.bundles_transferred += 1
                    hop = bundle.header.hop_count
                    _self._hop_counts.append(hop)
                    _self.metrics.max_hops = max(_self.metrics.max_hops, hop)
                    _self._emit(
                        "hop",
                        from_node=received_from,
                        to_node=_to,
                        bundle_id=bundle.id,
                        incident_id=bundle.header.incident_id,
                        hop=hop,
                        path=list(bundle.header.path),
                    )
                return stored, reason

            node.accept_bundle = wrapped  # type: ignore[method-assign]

    # ---------------------------------------------------------------- injection

    def inject_report(self, node_id: str, text: str, **kw) -> str:
        """A node reports an incident; announce it on the stream."""
        incident = self.mesh.nodes[node_id].report_incident(text, **kw)
        self.metrics.expected += 1
        self._emit(
            "bundle_injected",
            to_node=node_id,
            incident_id=incident.id,
        )
        return incident.id

    # --------------------------------------------------------------------- run

    def run(self, *, max_rounds: int = 50) -> MeshMetrics:
        """Gossip until the mesh is quiescent or ``max_rounds`` is reached.

        A round offers every carried bundle across every live link, both ways,
        then drains the medium. Delivery to a coordinator is checked each round.
        The run stops early the first round that moves nothing new.
        """
        for _ in range(max_rounds):
            self._round += 1
            before = self.metrics.bundles_transferred
            for a, b in list(self.mesh.radio.links):
                self.mesh.nodes[a].sync_with(b)
                self.mesh.radio.drain()
            self._check_delivery()
            if self.metrics.bundles_transferred == before:
                break  # quiescent: a full round moved nothing new
        self.metrics.rounds = self._round
        if self._hop_counts:
            self.metrics.avg_hops = round(sum(self._hop_counts) / len(self._hop_counts), 3)
        self._emit("quiescent")
        return self.metrics

    def _check_delivery(self) -> None:
        for coord_id in self._coordinators:
            store = self.mesh.nodes[coord_id].store
            for incident in store.list_incidents(limit=1000):
                if incident.id in self._delivered_incidents:
                    continue
                self._delivered_incidents.add(incident.id)
                self.metrics.delivered += 1
                self._emit("delivered", to_node=coord_id, incident_id=incident.id)


def run_epidemic(
    mesh: Mesh,
    topology: TopologySpec,
    *,
    sinks: list[Sink] | None = None,
    max_rounds: int = 50,
    step_delay: float = 0.0,
) -> tuple[MultihopRun, MeshMetrics]:
    """Convenience: emit topology, run to quiescence, return the run and metrics.

    The caller is expected to have injected at least one report before calling,
    or to inject via the returned run for finer control.
    """
    run = MultihopRun(mesh, topology, sinks=sinks, step_delay=step_delay)
    run.emit_topology()
    metrics = run.run(max_rounds=max_rounds)
    return run, metrics
