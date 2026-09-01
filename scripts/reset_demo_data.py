#!/usr/bin/env python3
"""Reset demo state: wipe the gateway database and reseed simulated resources.

Deliberately explicit: it names the file it will delete and refuses to run against a
database that is not the demo one unless --force is given.

    python3 scripts/reset_demo_data.py [--db ./dms_gateway.db] [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "protocol"))
sys.path.insert(0, str(ROOT / "backend"))

DEMO_DB_NAMES = {"dms_gateway.db", "demo.db", "test.db"}

RESOURCES = [
    ("res_amb_1", "AMBULANCE", "Ambulance 1"),
    ("res_boat_1", "RESCUE_BOAT", "Rescue Boat 1"),
    ("res_fire_1", "FIRE_UNIT", "Fire Unit 1"),
    ("res_med_1", "MEDICAL_TEAM", "Medical Team 1"),
    ("res_search_1", "SEARCH_TEAM", "Search Team 1"),
    ("res_shelter_1", "SHELTER", "Shelter North"),
    ("res_truck_1", "SUPPLY_TRUCK", "Supply Truck 1"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset DisasterMesh demo data")
    parser.add_argument("--db", default=str(ROOT / "dms_gateway.db"))
    parser.add_argument("--force", action="store_true", help="allow a non-demo filename")
    args = parser.parse_args()

    path = Path(args.db)
    if path.name not in DEMO_DB_NAMES and not args.force:
        print(f"refusing to delete {path} — not a known demo database (use --force)")
        return 2

    if path.exists():
        print(f"deleting {path} ({path.stat().st_size:,} bytes)")
        path.unlink()
    else:
        print(f"{path} does not exist — nothing to delete")

    from app import db as db_module

    db_module.reset_engine(f"sqlite:///{path}")
    db_module.init_db()

    session = db_module.session_factory()()
    try:
        for resource_id, kind, label in RESOURCES:
            session.add(
                db_module.ResourceRow(
                    id=resource_id,
                    organization_id="org_demo",
                    kind=kind,
                    label=label,
                    status="AVAILABLE",
                    simulated=True,
                    doc={
                        "id": resource_id,
                        "kind": kind,
                        "label": label,
                        "simulated": True,
                        "organization_id": "org_demo",
                    },
                )
            )
        session.commit()
    finally:
        session.close()

    print(f"seeded {len(RESOURCES)} simulated resources into {path}")
    print("all seeded resources are simulated; none maps to a real emergency unit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
