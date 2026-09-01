# Development Status

The single source of truth for what actually works. Nothing is marked VERIFIED without
a passing test or a documented manual run on this machine.

**Last updated:** 2026-09-01
**Verified on:** Windows PowerShell, Python 3.14.2; Android still blocked by local Java/SDK setup

## Legend

`NOT STARTED` - `WRITTEN` (code exists, never executed) - `IMPLEMENTED` (runs, partly
covered) - `VERIFIED` (tests pass) - `BLOCKED` (needs something this machine lacks)

## Test Results

Reproduce with `make test && make test-dashboard`:

| Suite | Command | Result |
|---|---|---|
| Core protocol & mesh | `cd protocol && python3 -m pytest` | **332 passed** in 1.4s |
| Gateway API | `cd backend && python3 -m pytest` | **53 passed** in 1.4s |
| AI service | `cd ai-service && python3 -m pytest tests` | **20 passed** in 0.5s |
| Dashboard | `cd dashboard && npm run test` | **13 passed** |
| Lint | `ruff check protocol backend ai-service scripts` | **clean** |
| Dashboard types | `cd dashboard && npx tsc --noEmit` | **clean** |
| Dashboard build | `npm run build` | **succeeds** (287 KB js, 85 KB gzipped) |
| Android | `cd android-app && .\gradlew.bat assembleDebug` | **BLOCKED - Android SDK not found** |

**418 automated tests pass. Zero known failures outside the documented Android/toolchain gaps.**

## Subsystems

| # | Subsystem | Status | Evidence |
|---|---|---|---|
| 1 | Repository guidance | VERIFIED | Local guidance docs and ignore rules |
| 2 | Domain models | VERIFIED | `test_domain.py` - 20 tests |
| 3 | Incident lifecycle | VERIFIED | full transition matrix + authorization tests |
| 4 | Local persistence (SQLite) | VERIFIED | `test_store.py` - migrations, idempotency, restart |
| 5 | DMBP bundle protocol | VERIFIED | `test_protocol.py` - 13 tests, all 8 invariants |
| 5a | Cross-language priority contract | VERIFIED | `test_priority_contract.py` (37 cases) + `test_engine_parity.py` (17 checks) |
| 6 | Cryptography | VERIFIED | `test_crypto.py` - 9 tests incl. tamper and revocation |
| 7 | Inventory exchange | VERIFIED | `test_inventory.py` - 11 tests |
| 8 | Transport abstraction | VERIFIED | mock transport drives every sync test |
| 9 | Nearby Connections adapter | **WRITTEN** | Android compile blocked by missing SDK; no physical radio test yet |
| 10 | Emergency Sync Engine | VERIFIED | `test_scheduler.py` - 11 tests, all 7 guarantees |
| 11 | File manifest + resumable transfer | VERIFIED | `test_files.py` - 15 tests |
| 12 | Acknowledgement & idempotency | VERIFIED | `test_e2e.py` |
| 13 | AI service (mock adapters) | VERIFIED | 20 API tests + 40 adapter tests |
| 14 | Rule triage & extraction (EN/HI/TA) | VERIFIED | `test_ai.py` - multilingual + code-switched |
| 15 | Priority engine | VERIFIED | `test_priority.py` - 16 tests incl. escalation floors |
| 16 | Context policies | VERIFIED | policy selection + battery shedding tests |
| 17 | Duplicate clustering | VERIFIED | `test_clustering.py` - 8 tests |
| 18 | Governance & authorization | VERIFIED | `test_governance.py` - 14 tests |
| 19 | Audit ledger | VERIFIED | tamper, deletion, and reorder detection |
| 20 | Dispatch simulation | VERIFIED | `test_dispatch.py` - 16 tests |
| 21 | Gateway API | VERIFIED | `test_backend.py` - 53 tests |
| 22 | Coordinator dashboard | IMPLEMENTED | 13 unit tests, type-checks, builds; live gateway browser run still manual |
| 23 | Offline simulator | VERIFIED | 10 scenarios + 13 regression tests |
| 23a | Multi-hop simulation + live mesh view | VERIFIED | `test_multihop.py` (8 tests), `test_mesh.py` (4 tests); driver streams a hop event log to the gateway, dashboard **Mesh** tab renders it |
| 23b | Image transfer bytes + audio-to-text compose | VERIFIED (web/gateway) | `test_media.py` (7 tests): inline image bytes stored/verified/served, audio transcribes and files as a normal incident; dashboard **Report** tab sends, evidence renders the real image |
| 24 | End-to-end MVP path | VERIFIED | `test_e2e.py` - all ten MVP criteria plus media multihop reconciliation |
| 25 | Mesh routing demo UI | VERIFIED VISUAL MODEL | TypeScript dashboard scenarios for multihop, relay failure rerouting, media resume, P0-first scheduling, congestion avoidance, store-carry-forward delivery, and relay rejoin deduplication; smooth playback, stage readouts, model tests, browser screenshots, and production build pass. This view is deterministic and is not wired to live radio/backend topology. |
| 26 | Android client | **WRITTEN** | 16 Kotlin files, 2,224 lines; Gradle reaches dependency resolution with IntelliJ JDK, then blocks because Android SDK is not installed/found |
| 27 | Docker Compose | **WRITTEN** | docker not installed here; never run |

## The Ten MVP Criteria

Each maps to a named test in `protocol/tests/test_e2e.py`:

| # | Criterion | Test | Result |
|---|---|---|---|
| 1 | A reporter creates a text incident | `test_1_reporter_creates_a_text_incident` | PASS |
| 2 | The incident receives a priority | `test_2_incident_receives_a_priority` | PASS |
| 3 | It is encrypted and stored locally | `test_3_incident_is_encrypted_and_stored_locally` | PASS |
| 4 | A nearby relay receives it | `test_4_and_5_relay_receives_and_forwards_to_coordinator` | PASS |
| 5 | The relay forwards it to a coordinator | same | PASS |
| 6 | The coordinator sees it | `test_6_coordinator_sees_the_incident_with_original_text` | PASS |
| 7 | An image can follow the text | `test_7_image_follows_the_text_and_is_verified` | PASS |
| 8 | The coordinator acknowledges it | `test_8_coordinator_acknowledges` | PASS |
| 9 | A simulated dispatch can be created | `test_9_simulated_dispatch_can_be_created` | PASS |
| 10 | It all works without Internet | `test_10_the_whole_flow_ran_with_no_internet` | PASS |

## Toolchain Gaps Requiring Human Action

- **No Android SDK found.** `ANDROID_HOME` is unset and no `sdk.dir` exists in
  `android-app/local.properties`, so the Kotlin module cannot compile yet.
- **Default Java is 8.** The build can be pointed at IntelliJ's bundled JDK, but a
  project-pinned JDK 17 or 21 is still the right long-term setup.
- **Docker is not installed**, so `docker-compose.yml` and both Dockerfiles are unverified.
- **No real model weights** were downloaded. Every AI path runs its deterministic
  fallback, which is also the production offline behaviour.
