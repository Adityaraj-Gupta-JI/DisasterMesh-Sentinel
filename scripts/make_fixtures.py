#!/usr/bin/env python3
"""Regenerate test fixtures from the live pipeline.

Fixtures are generated, never hand-written: if the classifier or the priority engine
changes, regenerating makes the drift visible in a diff instead of hiding it.

    python3 scripts/make_fixtures.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "protocol"))

from dms.sim.harness import build_demo_mesh  # noqa: E402

CASES = {
    "demo-medical-incident.json": "Three people trapped under collapsed building near Market Road, one is bleeding",
    "demo-flood-incident.json": "Water rising fast near the river bridge, families on rooftops",
    "demo-routine-incident.json": "Need drinking water at the shelter tomorrow",
}

MULTILINGUAL = [
    "மூன்று பேர் இடிந்த கட்டிடத்தில் சிக்கியுள்ளனர்",
    "बाढ़ का पानी बढ़ रहा है, मदद चाहिए",
]


def main() -> int:
    out = ROOT / "test-fixtures"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        mesh = build_demo_mesh(Path(tmp))
        node = mesh.nodes["A"]
        for name, text in CASES.items():
            incident = node.report_incident(text)
            (out / name).write_text(json.dumps(incident.to_dict(), indent=2, ensure_ascii=False))
            print(f"{name}: {incident.priority_class.value} score={incident.priority_score}")
        multilingual = [node.report_incident(text).to_dict() for text in MULTILINGUAL]
        (out / "demo-multilingual-incidents.json").write_text(
            json.dumps(multilingual, indent=2, ensure_ascii=False)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
