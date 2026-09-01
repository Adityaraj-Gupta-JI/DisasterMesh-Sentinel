# Local Development

## Requirements

| Tool | Version here | Needed for |
|---|---|---|
| Python | 3.13.9 | protocol, gateway, AI service |
| Node | 22.22 | dashboard |
| ruff | 0.12 | lint and format |
| Android SDK + Gradle | **absent** | the Android app (blocked) |
| Docker | **absent** | compose stack (unverified) |

Python packages used: `pytest`, `fastapi`, `pydantic`, `sqlalchemy`, `cryptography`.
All were already present in this environment; install with pip if yours differs.

## First run

```bash
make test        # 387 Python tests, ~4s total
make demo        # the whole product path, offline, in one command
```

## Running the services

```bash
make run-backend      # :8000, OpenAPI at /docs
make run-ai           # :8001, mock mode
make run-dashboard    # :5173
```

The dashboard reads `VITE_API_URL` and `VITE_API_KEY`; copy `dashboard/.env.example`
to `dashboard/.env` to change them. The gateway needs no configuration in development.

## Layout

```
protocol/dms/
  domain/      models, enums, lifecycle, clock, errors
  protocol/    DMBP bundles, inventory exchange
  crypto/      keystore, sealing
  transport/   abstraction + mock radio
  sync/        scheduler, wire engine
  files/       manifest, resumable transfer
  governance/  authorization, audit ledger
  priority/    deterministic engine, context policies
  ai/          lexicon, rules, mock adapters, clustering
  store/       SQLite persistence
  dispatch/    simulated dispatch service
  sim/         harness + ten scenarios
  node.py      composition root
```

## Testing

```bash
cd protocol && python3 -m pytest                    # everything
python3 -m pytest tests/test_e2e.py -v              # the MVP criteria, named
python3 -m pytest -k "priority or scheduler" -q     # one area
```

Tests use a `FixedClock`, the mock transport, and rule-based AI — so they are
deterministic and none of them touches a network.

## Android

Blocked here. To build it elsewhere you need `ANDROID_HOME`, a Gradle wrapper, and a
JDK 17 or 21 (the installed JDK 25 is newer than current AGP supports). Nothing about
the Kotlin has been compiled — start by expecting compile errors, not design errors.

## Conventions

- Small functions, typed models, explicit over clever.
- No business logic in UI; no direct DB access from UI.
- A comment explains *why*, never *what*.
- New behaviour arrives with a test; a bug fix arrives with the test that would have caught it.
- Significant trade-offs get an ADR in `docs/DECISIONS.md`.
