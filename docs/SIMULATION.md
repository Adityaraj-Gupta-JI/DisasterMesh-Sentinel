# Offline Network Simulator

Deterministic scenarios that hardware cannot be relied on to reproduce on demand.
Seeded, so a regression is reproducible.

```bash
make simulate                              # all ten, writes reports/
python3 scripts/run_simulator.py --only 3,7,8
```

Outputs `reports/simulation_results.json` and `reports/simulation_results.csv`.

## Scenarios and last measured results

| # | Scenario | Delivered | What it proves |
|---|---|---|---|
| 1 | A → B → C critical relay | 1/1 | The core path, with the relay unable to decrypt |
| 2 | Intermittent contacts | 1/1 | A link dropped mid-exchange loses nothing |
| 3 | P0 text vs a 2 MB P3 file | 1/1 | `P0 text preceded bulk media: True` |
| 4 | Gateway appears after 10 minutes | 1/1 | The mesh holds a report with no coordinator in range |
| 5 | Duplicate reports | 2/2 | Provisional cluster, `human_reviewed=False` |
| 6 | Unauthorized medical request | 0/0 | Two roles refused, with recorded reasons |
| 7 | Battery below threshold | 1/1 | P0 delivered at 5%, P3 deferred |
| 8 | File transfer interruption | 1/1 | Resumes and commits only after digest match |
| 9 | AI unavailable | 1/1 | `priority without AI: P0`, original text preserved |
| 10 | Conflicting reports | 2/2 | Disagreement surfaced, not averaged |

## Metrics

Delivery ratio, P0/P1 delivery delay, bundles transferred, duplicates suppressed, file
completion ratio, acknowledgement latency, unauthorized rejections, and a battery
estimate.

The battery figure is a crude model — bytes moved times a constant, plus a per-contact
cost. It is useful for comparing two scheduling policies against each other and useless
as an absolute prediction. It is labelled as an estimate everywhere it appears.

## Why the simulator earns its keep

Scenario 8 found a real bug: delivery was recorded when a bundle was *sent*, so a
transfer interrupted mid-flight was never re-offered and the report was silently lost.
No unit test caught it, because each unit was behaving correctly. ADR-0003 records the
fix. That single finding justified the whole component.
