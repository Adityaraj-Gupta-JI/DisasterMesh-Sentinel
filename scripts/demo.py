#!/usr/bin/env python3
"""End-to-end demo: reporter → relay → coordinator → simulated dispatch.

Runs the whole product path offline, on one machine, with no phones and no models.
Every line it prints is produced by the real subsystems, not staged output.

    python3 scripts/demo.py [--language en|hi|ta] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "protocol"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dms.ai.clustering import cluster  # noqa: E402
from dms.ai.mocks import summarize  # noqa: E402
from dms.dispatch.service import DispatchService, default_resources  # noqa: E402
from dms.domain.enums import AttachmentKind, DispatchStatus, Role  # noqa: E402
from dms.sim.harness import build_demo_mesh  # noqa: E402

REPORTS = {
    "en": "Three people trapped under collapsed building near Market Road, one is bleeding",
    "hi": "मार्केट रोड के पास गिरी हुई इमारत में तीन लोग फंसे हैं, एक को खून बह रहा है",
    "ta": "மார்க்கெட் சாலை அருகே இடிந்த கட்டிடத்தில் மூன்று பேர் சிக்கியுள்ளனர்",
}

SECOND_REPORT = "Building collapsed near the market, people trapped inside"
IMAGE = b"\xff\xd8\xff" + b"collapse-photo-bytes" * 6000


def step(number: int, title: str) -> None:
    print(f"\n\033[1m{number}. {title}\033[0m")


def main() -> int:
    parser = argparse.ArgumentParser(description="DisasterMesh Sentinel demo")
    parser.add_argument("--language", choices=sorted(REPORTS), default="en")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable summary")
    args = parser.parse_args()

    transcript: dict[str, object] = {}

    with tempfile.TemporaryDirectory() as tmp:
        mesh = build_demo_mesh(Path(tmp))
        reporter, relay, coordinator = mesh.nodes["A"], mesh.nodes["B"], mesh.nodes["C"]

        print("\033[1mDisasterMesh Sentinel — offline demo\033[0m")
        print("Reporter A (citizen) · Relay B (volunteer) · Coordinator C (event coordinator)")
        print("No internet. No radios. No model weights. Nothing is a real dispatch.")

        # ------------------------------------------------------------ report
        step(1, "A citizen reports an emergency, offline")
        text = REPORTS[args.language]
        incident = reporter.report_incident(text)
        print(f'   "{text}"')
        print(f"   language detected : {incident.source_language}")
        print(
            f"   priority          : {incident.priority_class.value} "
            f"(score {incident.priority_score}/100)"
        )
        print(
            f"   people affected   : {incident.people_affected.value if not incident.people_affected.is_unknown else 'unknown'}"
        )
        print(f"   categories        : {', '.join(t.value for t in incident.disaster_types)}")
        print("   why this priority :")
        for line in incident.priority_explanation:
            print(f"     - {line}")
        transcript["incident"] = incident.to_dict()

        # ---------------------------------------------------------- encrypted
        step(2, "The report is encrypted and stored on the phone")
        bundle = reporter.store.get_bundle(reporter.store.bundle_ids()[0])
        leak = any(
            word.encode() in bundle.payload for word in ("trapped", "bleeding", "फंसे", "சிக்கி")
        )
        print(f"   bundle id         : {bundle.id}")
        print(f"   encryption        : {bundle.header.encryption['alg']}")
        print(f"   signed by         : {bundle.header.signer_node_id}")
        print(f"   plaintext on disk : {'LEAKED' if leak else 'none — payload is ciphertext'}")

        # -------------------------------------------------------- attachment
        step(3, "The reporter attaches a photo — text still goes first")
        attachment = reporter.attach(
            incident.id,
            IMAGE,
            file_name="collapse.jpg",
            mime_type="image/jpeg",
            kind=AttachmentKind.IMAGE,
        )
        print(f"   attachment        : {attachment.file_name} ({attachment.size_bytes:,} bytes)")
        print(f"   sha-256           : {attachment.sha256[:24]}…")
        print(
            f"   queued bundles    : {len(reporter.store.bundle_ids())} "
            f"(1 text + 1 manifest + chunks)"
        )

        # ----------------------------------------------------------- relay
        step(4, "A volunteer's phone comes into range and carries it")
        mesh.connect("A", "B")
        mesh.exchange("A", "B")
        print(f"   B now holds       : {len(relay.store.bundle_ids())} bundles")
        print(f"   B can decrypt     : {relay.can_decrypt}")
        print(
            f"   B reconstructed   : {relay.store.count_incidents()} incidents "
            f"(it carries ciphertext it cannot read)"
        )

        # ------------------------------------------------------ coordinator
        step(5, "The volunteer reaches a coordinator")
        mesh.clock.advance(minutes=4)
        mesh.connect("B", "C")
        mesh.exchange("B", "C")
        received = coordinator.store.get_incident(incident.id)
        arrival = [
            coordinator.store.get_bundle(e["detail"]["bundle_id"]).header.payload_type.value
            for e in coordinator.store.events(incident.id)
            if e["action"] == "BUNDLE_RECEIVED"
        ]
        text_bundle = next(
            coordinator.store.get_bundle(b)
            for b in coordinator.store.bundle_ids()
            if coordinator.store.get_bundle(b).header.payload_type.value == "INCIDENT_TEXT"
        )
        print(f'   coordinator sees  : "{received.original_text[:60]}…"')
        print(f"   original preserved: {received.original_text == text}")
        print(f"   relay path        : {' → '.join(text_bundle.header.path)}")
        print(
            f"   arrival order     : {arrival[0]} first, then {arrival.count('ATTACHMENT_CHUNK')} media chunk(s)"
        )
        committed = coordinator.store.attachments_for(incident.id)
        print(f"   photo committed   : {bool(committed)} (digest verified before it was written)")

        # --------------------------------------------------------- duplicate
        step(6, "A second bystander reports the same event")
        mesh.clock.advance(minutes=2)
        reporter.report_incident(SECOND_REPORT)
        mesh.exchange("A", "B")
        mesh.exchange("B", "C")
        incidents = coordinator.store.list_incidents()
        grouped = cluster(incidents[0], incidents[1:]) if len(incidents) > 1 else None
        if grouped:
            print(
                f"   cluster decision  : {grouped.decision.value} "
                f"(similarity {grouped.similarity:.2f})"
            )
            print(f"   provisional       : {grouped.provisional} — a human confirms or splits it")
            for line in grouped.rationale:
                print(f"     - {line}")
        summary = summarize([i.to_dict() for i in incidents])
        print(
            f"   estimated affected: {summary.estimated_affected_people['value']} "
            f"({summary.estimated_affected_people['basis']})"
        )
        for note in summary.uncertainties:
            print(f"   uncertainty       : {note}")

        # ---------------------------------------------------- acknowledgement
        step(7, "The coordinator acknowledges")
        coordinator.acknowledge(incident.id, note="search team being assigned")
        print(f"   status            : {coordinator.store.get_incident(incident.id).status.value}")
        mesh.exchange("C", "B")
        mesh.exchange("B", "A")
        print(
            f"   reporter now sees : {reporter.store.get_incident(incident.id).status.value} "
            "— the person who called for help knows help heard"
        )

        # ---------------------------------------------------------- dispatch
        step(8, "A simulated dispatch, authorized by a human")
        service = DispatchService(coordinator.store, coordinator.event_log, coordinator.clock)
        for resource in default_resources():
            service.register_resource(resource)
        seen = coordinator.store.get_incident(incident.id)
        options = service.recommend(seen)
        for option in options:
            print(f"   recommended       : {option.resource.label} — {option.reason}")
        order = service.create_order(seen, options[0].resource.id, reason=options[0].reason)
        print(f"   order created     : {order.status.value} (creating one dispatches nothing)")
        service.authorize(
            order, seen, actor_node_id=coordinator.identity.id, actor_role=Role.EVENT_COORDINATOR
        )
        print(f"   after human OK    : {order.status.value}, simulated={order.simulated}")
        service.advance(order, DispatchStatus.ACKNOWLEDGED)
        service.advance(order, DispatchStatus.EN_ROUTE)
        print(f"   responder status  : {order.status.value}")

        # ------------------------------------------------------------- audit
        step(9, "The audit trail")
        events = coordinator.store.events(incident.id)
        for event in events:
            print(f"   {event['action']}")
        print(
            f"   ledger intact     : {coordinator.event_log.verify()} "
            "(hash-chained; an edit or deletion would show)"
        )

        step(10, "What never happened")
        print("   · no internet connection was used")
        print("   · no real emergency service was contacted")
        print("   · the AI never dispatched anything — it only proposed")
        print("   · the relay never read what it carried")
        print(
            f"   · the original wording was preserved byte for byte: "
            f"{coordinator.store.get_incident(incident.id).original_text == text}"
        )

        transcript.update(
            {
                "path": list(text_bundle.header.path),
                "arrival_order": arrival,
                "relay_could_decrypt": relay.can_decrypt,
                "acknowledged": coordinator.store.get_incident(incident.id).status.value,
                "dispatch_status": order.status.value,
                "dispatch_simulated": order.simulated,
                "audit_events": [e["action"] for e in events],
                "ledger_verified": coordinator.event_log.verify(),
            }
        )
        mesh.stop()

    if args.json:
        print("\n" + json.dumps(transcript, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
