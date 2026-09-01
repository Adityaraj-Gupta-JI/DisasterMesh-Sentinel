# DisasterMesh Sentinel

**An offline-first emergency information commons.** When the towers are down, a phone
can still take a report, decide how urgent it is, encrypt it, hand it to a stranger's
phone, and get it to a coordinator who can act — with a human, never a model, making
the decision at the end.

Status: **hackathon MVP, verified in software.** The mesh, protocol, priority engine,
sync, file transfer, governance, gateway, and dashboard all run and are tested.
The Android client is written but **has never been compiled** — see
[Known limitations](docs/KNOWN_LIMITATIONS.md).

---

## See it work in 30 seconds

```bash
make demo
```

No internet, no phones, no model weights. A citizen reports a building collapse; the
report is classified P0, encrypted, carried by a volunteer's phone that cannot read
it, delivered to a coordinator, acknowledged, and answered with a *simulated* dispatch
— every line printed by the real subsystems.

```bash
make demo-hindi      # the same flow, reported in Hindi
make demo-tamil      # …and in Tamil
make simulate        # ten adversarial network scenarios, JSON + CSV reports
make test            # 387 Python tests
```

## What it does

| | |
|---|---|
| **Offline-first** | Every capability except gateway sync works with no network at all. |
| **Text-first** | A P0 text bundle is independent of its photo. Media can never delay it. |
| **Severity-aware** | A deterministic engine scores 0–100 and explains every point. |
| **Human-supervised AI** | The model proposes; the policy engine decides; a person authorizes. |
| **Encrypted** | AES-256-GCM payloads, Ed25519-signed headers. Relays carry, and cannot read. |
| **Multilingual** | English, Hindi, and Tamil — including code-switched reports. |
| **Resumable** | Interrupted transfers resume; a file is committed only after its digest matches. |
| **Auditable** | A hash-chained ledger in which an edit or deletion is detectable. |

## Repository

```
protocol/      Reference implementation: domain, DMBP, crypto, sync, files,
               governance, priority engine, AI rules, simulator  (266 tests)
backend/       FastAPI gateway: incidents, dispatch, alerts, audit    (43 tests)
ai-service/    FastAPI inference service, mock adapters by default    (20 tests)
dashboard/     React + TypeScript coordinator dashboard                (8 tests)
android-app/   Kotlin + Jetpack Compose client            (NOT COMPILED — no SDK)
scripts/       demo.py · run_simulator.py · make_fixtures.py · reset_demo_data.py
docs/          Architecture, protocol, security, threat model, demo guide
test-fixtures/ Fixtures generated from the live pipeline, never hand-written
```

## The one idea worth stealing

> **The AI proposes. The policy engine decides. A human authorizes.**

A model that is 2% confident cannot downgrade "he is not breathing". A rule sets a
floor; only a coordinator can override it, and the override is recorded with a reason.

```
urgency LOW → base 8
severity 5 → +1
RULE: unconscious/not breathing → P0 floor 85
low AI confidence 0.02, no rule trigger → -4
rule floor raised score 5 → 85
```

That trace is printed with the incident, stored with it, and travels with it.

## Getting started

```bash
make help            # every available target
make test            # protocol + gateway + AI service
make run-backend     # gateway on :8000  (OpenAPI at /docs)
make run-ai          # AI service on :8001 in mock mode
make run-dashboard   # dashboard on :5173
```

Full setup, including the Android gap, is in [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md).

## Documentation

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | As-built architecture and layer boundaries |
| [PROTOCOL.md](docs/PROTOCOL.md) | DMBP bundle format, inventory exchange, invariants |
| [SECURITY.md](docs/SECURITY.md) | Crypto design, key handling, authorization model |
| [THREAT_MODEL.md](docs/THREAT_MODEL.md) | 15 attack paths, mitigations, and what is still open |
| [DEVELOPMENT_STATUS.md](docs/DEVELOPMENT_STATUS.md) | What is verified, what is merely written |
| [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) | Everything this prototype cannot do |
| [TRACEABILITY.md](docs/TRACEABILITY.md) | Requirement → implementation → test, for every MVP requirement |
| [DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) | The demo, with fallbacks for when things go wrong |
| [DECISIONS.md](docs/DECISIONS.md) | Architecture decision records |

## What this is not

This prototype **never contacts a real emergency service.** Every resource is
simulated and every dispatch order is labelled as such in the data model, the API, the
UI, and the audit log. It has not been through a security review by anyone other than
its own adversarial test suite, and it has not been tested on real radios between real
phones. Do not deploy it in an actual emergency.
