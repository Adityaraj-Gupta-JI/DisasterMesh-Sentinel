# Repository Audit

Recorded at the start of implementation and updated on completion, so the starting
point is not rewritten in hindsight.

## Starting state (2026-08-31, before implementation)

The working directory contained a guidance layer and nothing else:

- `CLAUDE.md`, `AGENTS.md`, `.gitignore`, `.env.example`, `Makefile`
- 8 agent definitions under `.claude/agents/`
- 6 documents under `docs/` — architecture (target state), contributing, decisions,
  development status, domain glossary, local development

No source code, no tests, no build system, no git history. Every `Makefile` target was
correctly reported as blocked.

## Toolchain found

| Present | Absent |
|---|---|
| Python 3.13.9, pytest 8.4, ruff 0.12 | Android SDK (`ANDROID_HOME` unset) |
| fastapi, pydantic 2, sqlalchemy, cryptography | Gradle and any wrapper |
| Node 22.22, npm 10.9 | Docker |
| JDK 25 | Model weights |
| git 2.55, make 4.4 | |

JDK 25 is newer than current AGP supports, so even with an SDK the Android build would
need a pinned JDK 17 or 21.

## End state

| Area | Files | Lines | Tests |
|---|---|---|---|
| `protocol/` | 78 Python | ~12,900 | 324 |
| `backend/` | included above | | 43 |
| `ai-service/` | included above | | 20 |
| `dashboard/` | 8 TS/TSX | 753 | 8 |
| `android-app/` | 16 Kotlin | 2,224 | 5 written, **0 run** |
| `docs/` | 34 documents | ~2,500 | — |

**395 automated tests pass.** Lint clean, dashboard type-check clean, dashboard builds.

## Honest gaps

The Android module and the Docker stack were written but never executed. That is
recorded in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) rather than glossed, and the
corresponding Makefile targets exit non-zero instead of appearing to pass.
