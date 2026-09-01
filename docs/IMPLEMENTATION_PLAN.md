# Implementation Plan

The plan that was followed, with outcomes. Kept for the record rather than rewritten to
match what happened.

## Strategy: contract-first, mock-first, vertical slice

```
domain contracts → mock offline flow → persistence → protocol → sync
→ UI → real transport → AI → governance → dispatch → audit
```

The mock transport came before any radio work, so the entire sync path could be tested
without hardware. That decision is why 324 core tests run in under two seconds and why
the Android gap costs verification of the radio layer only, not of the product logic.

## Phases and outcomes

| Phase | Scope | Outcome |
|---|---|---|
| 1 | Domain models, enums, lifecycle, clock | VERIFIED — 20 tests |
| 2 | DMBP protocol, canonical serialization | VERIFIED — 13 tests, 8 invariants |
| 3 | Crypto: Ed25519 signing, AES-GCM sealing | VERIFIED — 9 tests |
| 4 | Governance: roles, permissions, audit ledger | VERIFIED — 14 tests |
| 5 | Priority engine + context policies | VERIFIED — 16 tests |
| 6 | AI rules, lexicon, mock adapters | VERIFIED — 40 tests |
| 7 | Transport abstraction + mock radio | VERIFIED — drives every sync test |
| 8 | Persistence with migrations | VERIFIED — 15 tests |
| 9 | Sync engine + inventory exchange | VERIFIED — 11 + 11 tests |
| 10 | File manifest + resumable transfer | VERIFIED — 13 tests |
| 11 | MeshNode composition + e2e | VERIFIED — 22 tests, all MVP criteria |
| 12 | Dispatch simulation | VERIFIED — 16 tests |
| 13 | Clustering | VERIFIED — 8 tests |
| 14 | Simulator, 10 scenarios | VERIFIED — 13 regression tests |
| 15 | AI service | VERIFIED — 20 tests |
| 16 | Gateway API | VERIFIED — 43 tests |
| 17 | Dashboard | IMPLEMENTED — 8 tests, builds, not browser-tested |
| 18 | Android client | **WRITTEN — never compiled** |
| 19 | Docs, demo, fixtures | Complete |

## Feature phasing

**MVP (done):** offline reporting, priority, encryption, mesh relay, coordinator
acknowledgement, attachment transfer, simulated dispatch, audit, multilingual rules,
gateway, dashboard.

**Phase 2:** authenticated identity issuance (the root of most unmitigated threats),
Bloom-filter inventory, real model adapters, WebSocket push, PostgreSQL, Android on
hardware.

**Future:** cross-organisation federation, public alerting infrastructure, responder
mobile app, real dispatch integration — the last three behind explicit approval gates.

## What the plan got wrong

Three assumptions failed and were corrected during implementation, each recorded as an
ADR: coordinators were initially denied medical access (ADR-0002); delivery was recorded
optimistically on send (ADR-0003); clustering treated proximity as evidence (ADR-0005).
All three were found by tests or the simulator rather than by review.
