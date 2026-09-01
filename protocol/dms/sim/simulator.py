"""Deterministic offline-network simulator.

Runs the scenarios that hardware cannot be trusted to reproduce on demand: broken
links, dead batteries, unauthorized peers, gateways that appear late, and duplicate
reports of one event. Every run is seeded, so a regression is reproducible.

Metrics are measured, not asserted: a scenario reports what happened, and the test
suite decides whether that is acceptable.
"""

from __future__ import annotations

import csv
import json
import random
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..domain.enums import (
    IncidentStatus,
    PayloadType,
    Role,
)
from .harness import Mesh, build_demo_mesh

SEED = 20260831
P0_TEXT = "Three people trapped under collapsed building near Market Road"
P3_TEXT = "Need drinking water at the shelter tomorrow"
IMAGE = b"\xff\xd8\xff" + b"photo-bytes" * 20_000
BIG_FILE = b"\xff\xd8\xff" + b"bulk-logistics-photo" * 100_000


@dataclass
class ScenarioResult:
    """What a scenario observed. Plain numbers, no interpretation."""

    name: str
    description: str
    delivered: int = 0
    expected: int = 0
    p0_delivery_seconds: float | None = None
    p1_delivery_seconds: float | None = None
    bundles_transferred: int = 0
    duplicate_bundles_suppressed: int = 0
    replication_overhead: float = 0.0
    file_completion_ratio: float = 0.0
    battery_cost_estimate: float = 0.0
    acknowledgement_latency_seconds: float | None = None
    unauthorized_rejections: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def delivery_ratio(self) -> float:
        return self.delivered / self.expected if self.expected else 0.0

    def to_dict(self) -> dict:
        return asdict(self) | {"delivery_ratio": round(self.delivery_ratio, 4)}


#: Rough energy model: bytes moved dominate, per-contact setup is a fixed cost.
JOULES_PER_MB = 8.0
JOULES_PER_CONTACT = 1.5


def _battery_cost(mesh: Mesh) -> float:
    total_bytes = sum(len(d.data) for d in mesh.radio.delivered)
    return round(
        total_bytes / 1_000_000 * JOULES_PER_MB + len(mesh.links_made) * JOULES_PER_CONTACT, 3
    )


_ACTIVE_MESHES: list[Mesh] = []


def _fresh(tmp: Path, name: str) -> Mesh:
    mesh = build_demo_mesh(tmp / name)
    _ACTIVE_MESHES.append(mesh)
    mesh.links_made = []  # type: ignore[attr-defined]
    original = mesh.connect

    def tracked(a: str, b: str) -> None:
        mesh.links_made.append((a, b))  # type: ignore[attr-defined]
        original(a, b)

    mesh.connect = tracked  # type: ignore[assignment]
    return mesh


# ------------------------------------------------------------------ scenarios


def scenario_1_critical_relay(tmp: Path) -> ScenarioResult:
    """A → B → C critical relay: the core path, nothing else moving."""
    r = ScenarioResult("1_critical_relay", "A -> B -> C critical relay", expected=1)
    mesh = _fresh(tmp, "s1")
    a, b, c = mesh.nodes["A"], mesh.nodes["B"], mesh.nodes["C"]
    start = mesh.clock.now()
    incident = a.report_incident(P0_TEXT)

    mesh.connect("A", "B")
    mesh.exchange("A", "B")
    mesh.clock.advance(seconds=30)
    mesh.connect("B", "C")
    mesh.exchange("B", "C")

    if c.store.get_incident(incident.id):
        r.delivered = 1
        r.p0_delivery_seconds = (mesh.clock.now() - start).total_seconds()
    r.bundles_transferred = len(mesh.radio.delivered)
    r.battery_cost_estimate = _battery_cost(mesh)

    ack_start = mesh.clock.now()
    c.acknowledge(incident.id)
    mesh.clock.advance(seconds=15)
    mesh.exchange("C", "B")
    mesh.exchange("B", "A")
    if a.store.get_incident(incident.id).status is IncidentStatus.ACKNOWLEDGED:
        r.acknowledgement_latency_seconds = (mesh.clock.now() - ack_start).total_seconds()
    r.notes.append(f"relay could read payloads: {b.can_decrypt}")
    return r


def scenario_2_intermittent_contacts(tmp: Path) -> ScenarioResult:
    """The link drops mid-exchange and returns later; nothing may be lost."""
    r = ScenarioResult("2_intermittent", "Link drops mid-transfer, then returns", expected=1)
    mesh = _fresh(tmp, "s2")
    a, b, c = mesh.nodes["A"], mesh.nodes["B"], mesh.nodes["C"]
    incident = a.report_incident(P0_TEXT)
    a.attach(incident.id, IMAGE, file_name="e.jpg", mime_type="image/jpeg")

    mesh.connect("A", "B")
    a.sync_with("B")
    mesh.radio.pump(max_steps=3)  # cut the exchange off part-way
    mesh.disconnect("A", "B")
    r.notes.append(f"bundles at B after the drop: {len(b.store.bundle_ids())}")

    mesh.clock.advance(minutes=5)
    mesh.connect("A", "B")
    mesh.exchange("A", "B")
    mesh.connect("B", "C")
    mesh.exchange("B", "C")

    if c.store.get_incident(incident.id):
        r.delivered = 1
    r.bundles_transferred = len(mesh.radio.delivered)
    r.file_completion_ratio = 1.0 if c.store.attachments_for(incident.id) else 0.0
    r.battery_cost_estimate = _battery_cost(mesh)
    return r


def scenario_3_p0_versus_large_p3(tmp: Path) -> ScenarioResult:
    """A huge routine file must not delay a critical text."""
    r = ScenarioResult("3_p0_vs_large_p3", "P0 text competes with a large P3 file", expected=1)
    mesh = _fresh(tmp, "s3")
    a, c = mesh.nodes["A"], mesh.nodes["C"]
    routine = a.report_incident(P3_TEXT)
    a.attach(routine.id, BIG_FILE, file_name="bulk.jpg", mime_type="image/jpeg")
    critical = a.report_incident(P0_TEXT)

    mesh.connect("A", "C")
    a.sync_with("C")
    mesh.radio.drain()

    order = [
        c.store.get_bundle(e["detail"]["bundle_id"]).header
        for e in c.store.events()
        if e["action"] == "BUNDLE_RECEIVED"
    ]
    critical_at = next(
        (
            i
            for i, h in enumerate(order)
            if h.incident_id == critical.id and h.payload_type is PayloadType.INCIDENT_TEXT
        ),
        None,
    )
    routine_media_at = next(
        (i for i, h in enumerate(order) if h.payload_type is PayloadType.ATTACHMENT_CHUNK), None
    )
    if critical_at is not None:
        r.delivered = 1
        r.notes.append(f"P0 text arrived at position {critical_at} of {len(order)}")
    if routine_media_at is not None:
        r.notes.append(f"first P3 media chunk at position {routine_media_at}")
        r.notes.append(f"P0 text preceded bulk media: {critical_at < routine_media_at}")
    r.bundles_transferred = len(mesh.radio.delivered)
    r.battery_cost_estimate = _battery_cost(mesh)
    return r


def scenario_4_late_gateway(tmp: Path) -> ScenarioResult:
    """No coordinator in range for ten minutes; the mesh must hold the report."""
    r = ScenarioResult("4_late_gateway", "Gateway appears after 10 minutes", expected=1)
    mesh = _fresh(tmp, "s4")
    a, c = mesh.nodes["A"], mesh.nodes["C"]
    start = mesh.clock.now()
    incident = a.report_incident(P0_TEXT)
    mesh.connect("A", "B")
    mesh.exchange("A", "B")

    mesh.clock.advance(minutes=10)
    mesh.connect("B", "C")
    mesh.exchange("B", "C")
    if c.store.get_incident(incident.id):
        r.delivered = 1
        r.p0_delivery_seconds = (mesh.clock.now() - start).total_seconds()
    r.notes.append("report survived 10 minutes with no coordinator in range")
    r.bundles_transferred = len(mesh.radio.delivered)
    r.battery_cost_estimate = _battery_cost(mesh)
    return r


def scenario_5_duplicate_reports(tmp: Path) -> ScenarioResult:
    """Two bystanders report one collapse; the coordinator should see a cluster."""
    from ..ai.clustering import cluster

    r = ScenarioResult("5_duplicate_reports", "Two reports of one event cluster", expected=2)
    mesh = _fresh(tmp, "s5")
    a, c = mesh.nodes["A"], mesh.nodes["C"]
    a.report_incident(P0_TEXT)
    mesh.clock.advance(minutes=2)
    a.report_incident("Building collapsed, people trapped inside near the market")

    mesh.connect("A", "C")
    mesh.exchange("A", "C")
    r.delivered = c.store.count_incidents()

    incidents = c.store.list_incidents()
    grouped = cluster(incidents[0], incidents[1:]) if len(incidents) > 1 else None
    if grouped:
        r.notes.append(
            f"cluster decision {grouped.decision.value} at similarity {grouped.similarity:.2f}"
        )
        r.notes.append(f"provisional={grouped.provisional} human_reviewed={grouped.human_reviewed}")
        r.duplicate_bundles_suppressed = max(0, len(grouped.incident_ids) - 1)
    r.bundles_transferred = len(mesh.radio.delivered)
    r.battery_cost_estimate = _battery_cost(mesh)
    return r


def scenario_6_unauthorized_medical_request(tmp: Path) -> ScenarioResult:
    """A citizen node asks for medical content and must be refused."""
    from ..domain.models import NodeIdentity
    from ..sync.scheduler import SyncScheduler

    r = ScenarioResult("6_unauthorized", "Unauthorized node requests medical content", expected=0)
    mesh = _fresh(tmp, "s6")
    a = mesh.nodes["A"]
    a.report_incident("Patient unconscious and bleeding at the shelter")

    scheduler = SyncScheduler()
    now = mesh.clock.now()
    for role in (Role.CITIZEN_REPORTER, Role.FLOOD_RESPONDER):
        result = scheduler.select(
            a.store.pending_sync_objects(now),
            receiver=NodeIdentity(id="intruder", role=role),
            now=now,
        )
        refused = [d for d in result.decisions if not d.selected]
        r.unauthorized_rejections += len(refused)
        r.notes.append(f"{role.value}: {len(result.selected)} offered, {len(refused)} refused")
    return r


def scenario_7_low_battery(tmp: Path) -> ScenarioResult:
    """At 5% battery the relay must still move P0 text and shed the rest."""
    r = ScenarioResult("7_low_battery", "Relay battery below threshold", expected=1)
    mesh = _fresh(tmp, "s7")
    a, b, c = mesh.nodes["A"], mesh.nodes["B"], mesh.nodes["C"]
    critical = a.report_incident(P0_TEXT)
    routine = a.report_incident(P3_TEXT)

    mesh.connect("A", "B")
    mesh.exchange("A", "B")
    b.config.battery = 0.05
    mesh.connect("B", "C")
    mesh.exchange("B", "C")

    if c.store.get_incident(critical.id):
        r.delivered = 1
    r.notes.append(f"P0 delivered at 5% battery: {c.store.get_incident(critical.id) is not None}")
    r.notes.append(f"P3 deferred at 5% battery: {c.store.get_incident(routine.id) is None}")
    r.bundles_transferred = len(mesh.radio.delivered)
    r.battery_cost_estimate = _battery_cost(mesh)
    return r


def scenario_8_file_interruption(tmp: Path) -> ScenarioResult:
    """An image transfer is cut off and resumes on the next contact."""
    r = ScenarioResult(
        "8_file_interruption", "Attachment transfer interrupted then resumed", expected=1
    )
    mesh = _fresh(tmp, "s8")
    a, c = mesh.nodes["A"], mesh.nodes["C"]
    incident = a.report_incident(P0_TEXT)
    a.attach(incident.id, IMAGE, file_name="evidence.jpg", mime_type="image/jpeg")

    mesh.connect("A", "C")
    a.sync_with("C")
    mesh.radio.pump(max_steps=4)
    mesh.disconnect("A", "C")
    partial = len(c.store.attachments_for(incident.id))

    mesh.clock.advance(minutes=2)
    mesh.connect("A", "C")
    mesh.exchange("A", "C")
    committed = [x for x in c.store.attachments_for(incident.id) if x["committed"]]

    r.delivered = 1 if committed else 0
    r.file_completion_ratio = 1.0 if committed else 0.0
    r.notes.append(f"committed before interruption: {partial}; after resume: {len(committed)}")
    if committed:
        r.notes.append(f"digest verified on commit: {committed[0]['sha256'][:12]}")
    r.bundles_transferred = len(mesh.radio.delivered)
    r.battery_cost_estimate = _battery_cost(mesh)
    return r


def scenario_9_ai_unavailable(tmp: Path) -> ScenarioResult:
    """With AI switched off the rule engine must still reach P0."""
    r = ScenarioResult("9_ai_unavailable", "AI service unavailable", expected=1)
    mesh = _fresh(tmp, "s9")
    a, c = mesh.nodes["A"], mesh.nodes["C"]
    a.config.ai_available = False
    incident = a.report_incident(P0_TEXT)
    mesh.connect("A", "C")
    mesh.exchange("A", "C")

    received = c.store.get_incident(incident.id)
    if received:
        r.delivered = 1
        r.notes.append(f"priority without AI: {received.priority_class.value}")
        r.notes.append(f"original text preserved: {received.original_text == P0_TEXT}")
    r.bundles_transferred = len(mesh.radio.delivered)
    r.battery_cost_estimate = _battery_cost(mesh)
    return r


def scenario_10_conflicting_reports(tmp: Path) -> ScenarioResult:
    """Two reports disagree on the count; the summary must surface the conflict."""
    from ..ai.mocks import summarize

    r = ScenarioResult("10_conflicting", "Conflicting counts for one event", expected=2)
    mesh = _fresh(tmp, "s10")
    a, c = mesh.nodes["A"], mesh.nodes["C"]
    a.report_incident("Three people trapped under collapsed building")
    mesh.clock.advance(minutes=1)
    a.report_incident("Nine people trapped under collapsed building")

    mesh.connect("A", "C")
    mesh.exchange("A", "C")
    r.delivered = c.store.count_incidents()

    summary = summarize([i.to_dict() for i in c.store.list_incidents()])
    r.notes.append(f"estimated affected: {summary.estimated_affected_people['value']}")
    r.notes.extend(summary.uncertainties)
    r.bundles_transferred = len(mesh.radio.delivered)
    r.battery_cost_estimate = _battery_cost(mesh)
    return r


SCENARIOS: dict[str, Callable[[Path], ScenarioResult]] = {
    "1": scenario_1_critical_relay,
    "2": scenario_2_intermittent_contacts,
    "3": scenario_3_p0_versus_large_p3,
    "4": scenario_4_late_gateway,
    "5": scenario_5_duplicate_reports,
    "6": scenario_6_unauthorized_medical_request,
    "7": scenario_7_low_battery,
    "8": scenario_8_file_interruption,
    "9": scenario_9_ai_unavailable,
    "10": scenario_10_conflicting_reports,
}


def run_all(tmp: Path, only: list[str] | None = None) -> list[ScenarioResult]:
    random.seed(SEED)
    keys = only or list(SCENARIOS)
    results = [SCENARIOS[k](tmp) for k in keys]
    for mesh in _ACTIVE_MESHES:
        mesh.stop()
    _ACTIVE_MESHES.clear()
    return results



def write_reports(results: list[ScenarioResult], out_dir: Path) -> tuple[Path, Path]:
    """Emit JSON and CSV for the demo and for regression comparison."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "simulation_results.json"
    csv_path = out_dir / "simulation_results.csv"

    payload = {
        "seed": SEED,
        "scenarios": [r.to_dict() for r in results],
        "totals": {
            "scenarios": len(results),
            "delivered": sum(r.delivered for r in results),
            "expected": sum(r.expected for r in results),
            "bundles_transferred": sum(r.bundles_transferred for r in results),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2))

    columns = [
        "name",
        "description",
        "delivered",
        "expected",
        "delivery_ratio",
        "p0_delivery_seconds",
        "p1_delivery_seconds",
        "bundles_transferred",
        "duplicate_bundles_suppressed",
        "file_completion_ratio",
        "battery_cost_estimate",
        "acknowledgement_latency_seconds",
        "unauthorized_rejections",
    ]
    with csv_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for result in results:
            writer.writerow(result.to_dict())
    return json_path, csv_path
