# CLAUDE.md — DisasterMesh Sentinel

Control document for every coding agent working in this repository. Keep it short,
accurate, and current. If an instruction here is wrong, fix this file first.

## 1. Product

**DisasterMesh Sentinel** — an offline-first emergency communication and coordination
platform. It converts text, multilingual voice, images, and files into prioritized
incident bundles, relays them device-to-device through nearby phones, and drives
human-governed responder workflows.

### MVP boundary (do not exceed before it works end to end)

1. Reporter creates a text incident.
2. Incident receives a priority.
3. Incident is encrypted and stored locally.
4. A nearby relay receives it.
5. Relay forwards it to a coordinator.
6. Coordinator sees it.
7. An image can follow the text.
8. Coordinator acknowledges it.
9. A *simulated* dispatch action can be created.
10. Everything above works with no Internet.

Anything beyond these ten items is Phase 2 or later. Do not build it first.

## 2. Core invariants

1. P0 critical **text** is never blocked by image, audio, video, or routine sync.
2. The system keeps working when AI, Internet, backend, or gateway are unavailable.
3. AI **recommends**. AI never dispatches resources and never publishes public alerts.
4. Every incident retains original user input, original language, and provenance.
5. Every bundle has a stable ID, expiry, payload hash, and deduplication behavior.
6. Sensitive data is gated by an explicit access policy (relays are not readers).
7. Duplicate operations are idempotent.
8. No destructive migration, deletion, credential exposure, or broad refactor
   without explicit human approval.
9. No new dependency without a stated justification.
10. No feature is reported as working until a test or a documented manual run proves it.
11. The prototype never contacts a real emergency service.

## 3. Repository structure

Planned layout (created stage by stage — see `docs/WORK_GRAPH.md`):

```
android-app/    Kotlin + Jetpack Compose client (reporter / relay / coordinator)
backend/        FastAPI gateway + coordinator API
ai-service/     FastAPI inference service (mock adapters first)
dashboard/      React + TypeScript + Vite coordinator dashboard
protocol/       DMBP bundle protocol contracts + reference implementation
docs/           Architecture, decisions, status, threat model, demos
scripts/        Dev and demo helper scripts
test-fixtures/  Deterministic fixtures (incidents, audio, bundles)
.claude/agents/ Specialized subagent definitions
```

Only `docs/` and `.claude/` exist today. See `docs/DEVELOPMENT_STATUS.md` for the truth.

## 4. Commands

Verified on this machine (2026-08-31). Run `make help` for the current list.
Targets fail loudly with a clear message when their subproject does not exist yet.

| Purpose            | Command              | Status                                   |
|--------------------|----------------------|------------------------------------------|
| List targets       | `make help`          | works                                    |
| Backend tests      | `make test-backend`  | blocked — `backend/` not scaffolded      |
| AI service tests   | `make test-ai`       | blocked — `ai-service/` not scaffolded   |
| Dashboard build    | `make build-dashboard` | blocked — `dashboard/` not scaffolded  |
| Python lint/format | `make lint` / `make fmt` | ruff 0.12.0 available                |
| Android debug APK  | `make apk`           | **blocked** — no Gradle, no cmdline-tools |

### Toolchain present

`git 2.55` · `python3 3.13.9` · `pip 25.3` · `node 22.22` · `npm 10.9` ·
`java 25.0.4` · `make 4.4` · `ruff 0.12` · `pytest 8.4`

### Toolchain gaps (human action required)

- `gradle` is not installed and no Gradle wrapper exists yet.
- Android SDK exists at `~/Android/Sdk` (platform `android-37.0`, build-tools `36.0.0`)
  but `ANDROID_HOME` is unset and `cmdline-tools` is missing.
- JDK 25 is newer than what current AGP releases officially support; a pinned JDK
  (17 or 21) will likely be needed for Android builds.
- `docker` is not installed — Docker Compose workflows cannot be verified here.

Do not write Android build instructions as if they were verified. They are not.

## 5. Conventions

- Domain-driven modules. Clear seams between transport, sync, AI, governance, UI.
- No business logic in Compose screens. No direct DB access from UI.
- No model-specific logic inside the priority engine — the engine consumes a
  normalized AI result, never a model handle.
- Every network operation has a timeout, a retry policy, and a cancellation path.
- Every AI output is untrusted input until policy evaluation.
- Typed models everywhere (Kotlin data classes, Pydantic, Zod). Small functions.
- Consistent domain names across Kotlin / Python / TypeScript — see `docs/DOMAIN_GLOSSARY.md`.
- Prefer explicit and boring over clever.

## 6. Security restrictions

- Never commit secrets. `.env` is git-ignored; `.env.example` holds placeholders only.
- Never log plaintext incident content, medical detail, or precise location by default.
- Never disable a security check to make a test pass.
- Validate size and MIME on every uploaded or received file. Never execute one.
- Verify hashes before committing a received file into permanent storage.
- Public alerts and dispatch require an authorized role plus explicit human confirmation.

## 7. Working method (per task)

1. Inspect the repo and relevant docs.
2. State current implementation status briefly.
3. Pick the smallest safe slice.
4. Write or update a plan before editing.
5. Implement in small coherent changes.
6. Run the narrowest relevant test first.
7. Run format, lint, type check, build.
8. Review the diff.
9. Update `docs/DEVELOPMENT_STATUS.md`; add an ADR to `docs/DECISIONS.md` for any
   significant trade-off.
10. Report: files changed, commands run, results, limitations, next step.

Stop only when acceptance criteria are verified, or when blocked by a missing
credential, missing hardware, a human decision, or a scope change. Compiling is
not verification.

## 8. Output format

```
## Status
## Changes
## Verification
## Known limitations
## Next action
```

## 9. Human approval gates

Ask before: adding heavy model dependencies; destructive schema change; integrating
any real emergency API; enabling public alerts; enabling background radio behavior;
collecting personal medical data; deploying cloud inference over sensitive data;
changing the cryptographic design.
