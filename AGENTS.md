# AGENTS.md

Cross-agent entry point for DisasterMesh Sentinel (Claude Code, Antigravity, Cursor,
Codex, Windsurf, and similar agentic environments).

**Read `CLAUDE.md` first.** It is the authoritative control document: product scope,
core invariants, repository layout, real commands, conventions, security rules,
working method, and approval gates. This file only adds routing information.

## Specialized roles

Definitions live in `.claude/agents/`. Each states role, scope, allowed files,
forbidden actions, required tests, and output format.

| Agent | Owns |
|---|---|
| `android-engineer` | `android-app/` — Compose UI, Room, WorkManager, Keystore wiring |
| `backend-engineer` | `backend/` — FastAPI gateway, persistence, authz, audit |
| `ai-ml-engineer` | `ai-service/` — inference adapters, mock models, model registry |
| `network-protocol-engineer` | `protocol/` — DMBP bundles, inventory exchange, dedup |
| `security-reviewer` | crypto, governance, threat model — review authority, no feature work |
| `qa-engineer` | tests, simulator, fixtures |
| `ux-engineer` | design system, screen flows, accessibility |
| `documentation-engineer` | `docs/`, README, diagrams |

## Parallelism

Serialize until domain contracts and the DMBP schema are frozen. After that,
`backend/`, `dashboard/`, `android-app/`, `ai-service/`, tests, and docs may proceed
in parallel — but a shared contract change requires an ADR in `docs/DECISIONS.md`
and is resolved by the lead agent only, never inside a parallel worker.

## Non-negotiables

Offline-first · P0 text before media · AI proposes, policy decides · human-confirmed
dispatch · preserved provenance · idempotent operations · no real emergency system
is ever contacted.
