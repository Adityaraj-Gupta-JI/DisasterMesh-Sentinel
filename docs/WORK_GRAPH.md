# Work Graph

Dependency order actually used. Every task is complete unless marked otherwise.

| ID | Task | Depends on | Type | Verification | Status |
|---|---|---|---|---|---|
| T01 | Repository guidance | — | SEQUENTIAL | files exist | done |
| T02 | Domain models + enums | T01 | SEQUENTIAL | `test_domain.py` | done |
| T03 | Lifecycle rules | T02 | SEQUENTIAL | transition matrix tests | done |
| T04 | DMBP bundles | T02 | SEQUENTIAL | `test_protocol.py` | done |
| T05 | Cryptography | T04 | SEQUENTIAL | `test_crypto.py` | done |
| T06 | Governance + audit | T02 | PARALLEL | `test_governance.py` | done |
| T07 | Priority engine | T02 | PARALLEL | `test_priority.py` | done |
| T08 | AI rules + lexicon | T02 | PARALLEL | `test_ai.py` | done |
| T09 | Transport abstraction | T01 | PARALLEL | mock drives sync tests | done |
| T10 | Persistence | T02 | SEQUENTIAL | `test_store.py` | done |
| T11 | Inventory exchange | T04 | SEQUENTIAL | `test_inventory.py` | done |
| T12 | Sync scheduler | T07, T06 | SEQUENTIAL | `test_scheduler.py` | done |
| T13 | Sync wire engine | T11, T12, T09 | SEQUENTIAL | `test_e2e.py` | done |
| T14 | File transfer | T04, T10 | SEQUENTIAL | `test_files.py` | done |
| T15 | MeshNode | T05, T10, T13, T14 | SEQUENTIAL | `test_e2e.py` | done |
| T16 | Dispatch simulation | T15, T06 | SEQUENTIAL | `test_dispatch.py` | done |
| T17 | Clustering | T08 | PARALLEL | `test_clustering.py` | done |
| T18 | Simulator | T15 | SEQUENTIAL | `test_simulator.py` | done |
| T19 | AI service | T08 | PARALLEL | `test_ai_service.py` | done |
| T20 | Gateway API | T02, T06, T16 | PARALLEL | `test_backend.py` | done |
| T21 | Dashboard | T20 | PARALLEL | vitest + build | done |
| T22 | Android client | T02–T15 mirrored | BLOCKED | needs SDK | **written, not compiled** |
| T23 | Docs + demo + fixtures | all | SEQUENTIAL | `make demo`, `make simulate` | done |
| T24 | Real model adapters | T19 | HUMAN_APPROVAL | — | not started |
| T25 | Identity issuance | T06 | HUMAN_APPROVAL | — | not started |

## Critical path

T02 → T04 → T05 → T10 → T12 → T13 → T15 → T18/T20. Everything else hangs off it.

## Rollback

Every task is additive within its own module. The riskiest changes — the permission
matrix, delivery accounting, clustering weights, and the gateway document shape — each
have an ADR and a test that fails if reverted.
