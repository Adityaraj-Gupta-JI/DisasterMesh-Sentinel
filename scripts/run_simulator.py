#!/usr/bin/env python3
"""Run the DisasterMesh offline simulator and write JSON + CSV reports.

python3 scripts/run_simulator.py [--out reports] [--only 1,3,7]
"""

from __future__ import annotations

import argparse
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

from dms.sim.simulator import run_all, write_reports  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="DisasterMesh Sentinel simulator")
    parser.add_argument("--out", default=str(ROOT / "reports"), help="report output directory")
    parser.add_argument("--only", default="", help="comma-separated scenario numbers")
    args = parser.parse_args()

    only = [s.strip() for s in args.only.split(",") if s.strip()] or None
    with tempfile.TemporaryDirectory() as tmp:
        results = run_all(Path(tmp), only)

    print(f"{'scenario':24s} {'delivered':>12s} {'bundles':>8s}  notes")
    print("-" * 100)
    for r in results:
        print(
            f"{r.name:24s} {r.delivered:>5d}/{r.expected:<6d} {r.bundles_transferred:>8d}  "
            f"{r.notes[0] if r.notes else ''}"
        )
        for note in r.notes[1:]:
            print(f"{'':24s} {'':12s} {'':8s}  {note}")

    json_path, csv_path = write_reports(results, Path(args.out))
    print(f"\nwrote {json_path}\nwrote {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
