# Development Status

Single source of truth for what actually exists. Update after every milestone.
Never mark something verified without a passing test or a documented manual run.

**Last updated:** 2026-08-31
**Stage:** 1 of 19 — repository guidance system

## Legend

`NOT STARTED` · `IN PROGRESS` · `IMPLEMENTED` (code exists, untested) ·
`VERIFIED` (test or documented manual run passes) · `BLOCKED`

## Subsystems

| # | Subsystem | Status | Evidence |
|---|---|---|---|
| 1 | Repository guidance (CLAUDE.md, agents, docs) | IMPLEMENTED | this commit |
| 2 | Repository audit + architecture plan | NOT STARTED | — |
| 3 | Work graph | NOT STARTED | — |
| 4 | Monorepo scaffold | NOT STARTED | — |
| 5 | Mock-first offline flow (A→B→C) | NOT STARTED | — |
| 6 | Domain models | NOT STARTED | — |
| 7 | Local persistence (Room) | NOT STARTED | — |
| 8 | DMBP bundle protocol | NOT STARTED | — |
| 9 | Inventory exchange | NOT STARTED | — |
| 10 | Transport abstraction + MockTransport | NOT STARTED | — |
| 11 | Nearby Connections adapter | BLOCKED | no Gradle wrapper / ANDROID_HOME unset |
| 12 | Emergency Sync Engine | NOT STARTED | — |
| 13 | File manifest + resumable transfer | NOT STARTED | — |
| 14 | Lifecycle + acknowledgement | NOT STARTED | — |
| 15 | AI service skeleton (mock adapters) | NOT STARTED | — |
| 16 | Triage / entities / embeddings / translation | NOT STARTED | — |
| 17 | AI → priority engine integration | NOT STARTED | — |
| 18 | Design system + reporter/relay/coordinator UI | NOT STARTED | — |
| 19 | Backend API | NOT STARTED | — |
| 20 | Coordinator dashboard | NOT STARTED | — |
| 21 | Resource + simulated dispatch | NOT STARTED | — |
| 22 | Governance and roles | NOT STARTED | — |
| 23 | Cryptography | NOT STARTED | — |
| 24 | Offline network simulator | NOT STARTED | — |
| 25 | End-to-end + property tests | NOT STARTED | — |
| 26 | Security review / release gate | NOT STARTED | — |

## MVP acceptance criteria

None verified yet.

| # | Criterion | Status |
|---|---|---|
| 1 | Reporter creates a text incident | NOT STARTED |
| 2 | Incident receives a priority | NOT STARTED |
| 3 | Incident is encrypted and stored locally | NOT STARTED |
| 4 | A nearby relay receives it | NOT STARTED |
| 5 | Relay forwards it to a coordinator | NOT STARTED |
| 6 | Coordinator sees it | NOT STARTED |
| 7 | An image can follow the text | NOT STARTED |
| 8 | Coordinator acknowledges it | NOT STARTED |
| 9 | Simulated dispatch action can be created | NOT STARTED |
| 10 | Usable with no Internet | NOT STARTED |

## Known blockers

- **Android build.** `gradle` not installed, no Gradle wrapper committed,
  `ANDROID_HOME` unset. SDK exists at `~/Android/Sdk` (platform `android-37.0`,
  build-tools `36.0.0`) but `cmdline-tools` is absent. JDK 25 is likely too new for
  current AGP — a pinned JDK 17/21 will probably be required. Human action needed.
- **Docker.** Not installed; Compose-based workflows cannot be verified here.
- **Physical device testing.** Nearby Connections cannot be validated in this
  environment. Any claim of real radio behavior is unsupported until run on hardware.
