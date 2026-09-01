# DisasterMesh Sentinel — QA, Security & DevSecOps Audit

**Date:** 2026-08-31 · **Scope:** full repository + running gateway and AI service
**Method:** static inspection + safe live negative testing against local instances
**Data:** synthetic only · **Project files modified:** none (this report only)

> **Auditor independence:** this audit was performed by the same agent that wrote the
> code. That is a real conflict of interest. It is mitigated by preferring executed
> checks over assertions — every finding below is reproducible from a command — but an
> independent review is still warranted before any deployment.

---

## 1. Executive result

**HOLD RELEASE.**

The mesh core is in good shape: 395 tests pass, cross-tenant isolation holds, injection
and mass-assignment attempts failed, and no secrets or incident content reached logs.

Three issues block release. The most serious is **QA-001**: any authenticated
low-privilege reporter can permanently disable the coordinator's priority inbox with a
single request, and the damage survives a restart. There is also **no CI/CD pipeline of
any kind** and **no rate limiting anywhere**.

| Severity | Count |
|---|---|
| P0 | 0 |
| P1 | 3 |
| P2 | 6 |
| P3 | 3 |
| Informational | 4 |

---

## 2. Findings by severity

### QA-001 · Stored deep-nested JSON permanently breaks the coordinator inbox
- **Severity:** P1 · **Category:** Availability / Input validation · **Status:** Verified · **Confidence:** High
- **Evidence:** gateway log — `PydanticSerializationError: Error serializing to JSON:
  ValueError: Circular reference detected (depth exceeded)` raised from
  `serialize_response` on `GET /v1/incidents`.
- **Reproduction:**
  ```bash
  DEEP=$(python3 -c "print('{\"a\":'*400 + '1' + '}'*400)")
  curl -H "Authorization: Bearer dev-reporter-key" -H "Content-Type: application/json" \
       -X POST localhost:8000/v1/incidents \
       -d "{\"source_node_id\":\"n\",\"original_text\":\"deep\",\"people_affected\":$DEEP}"
  curl -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer dev-coordinator-key" \
       localhost:8000/v1/incidents        # -> 500, permanently
  ```
- **Expected:** the nested object is rejected at validation, or clamped on read.
- **Actual:** accepted with `201`, then `GET /v1/incidents` and `GET /v1/sync/pull`
  return `500` on every subsequent call. Confirmed to survive a full process restart —
  the poison pill is in the database.
- **Impact:** denial of service on the primary operational surface. A citizen-reporter
  credential — the lowest privilege in the system — silently disables the queue that
  coordinators triage from. Recovery requires manual database surgery.
- **Blast radius (measured):** `GET /v1/incidents` 500 · `GET /v1/sync/pull` 500 ·
  `GET /v1/incidents/{id}` 200 (unaffected) · `GET /v1/stats` 200 (unaffected) ·
  **the mesh itself is unaffected** — `_incident_from_doc` extracts scalar fields only
  and discards the nesting, verified by direct test.
- **Why P1 and not P0:** the gateway is optional by design; phones keep working. Were
  the gateway the primary surface, this would be P0.
- **Root cause:** `IncidentCreate.people_affected: dict[str, Any] | None` in
  `backend/app/schemas.py` accepts arbitrary structure with no depth or size bound.
  Same pattern in `conditions: list[dict[str, Any]]` and `SummarizeRequest.incidents`.
- **Fix:** replace the free-form dicts with typed models —
  `class QuantityIn(BaseModel): value: int | None = Field(None, ge=0); raw: str | None =
  Field(None, max_length=200); approximate: bool = False; confidence: float | None =
  Field(None, ge=0, le=1)` — and reject unknown keys with `model_config =
  ConfigDict(extra="forbid")`.
- **Verification test:** the reproduction above must return `422`, and
  `GET /v1/incidents` must stay `200`. Add it to `backend/tests/test_backend.py`.

### QA-002 · No CI/CD pipeline exists
- **Severity:** P1 · **Category:** DevSecOps · **Status:** Verified · **Confidence:** High
- **Evidence:** `.github/` does not exist. The only YAML in the repository is
  `docker-compose.yml`. `docs/REPOSITORY_AUDIT.md` lists "CI configuration" as inspected,
  and `docs/WORK_GRAPH.md` names verification commands, but nothing runs them automatically.
- **Impact:** every check is manual. Nothing prevents a merge that breaks the tests,
  reintroduces a fixed bug, or ships a lint failure. The drift guard added for the
  Kotlin/Python engines only protects anyone who remembers to run `make parity`.
- **Fix:** a `.github/workflows/ci.yml` running `make lint`, `make test`,
  `make test-dashboard`, `make parity`, and `make simulate` on push and pull request,
  with pinned action SHAs and least-privilege `permissions:`.
- **Verification:** open a pull request with a deliberately failing test; CI must block it.

### QA-003 · No rate limiting on any endpoint
- **Severity:** P1 · **Category:** Security / Availability · **Status:** Verified · **Confidence:** High
- **Evidence:** 30 rapid unauthenticated requests to `/v1/incidents` returned
  `30 × 401`, `0 × 429`. No limiter middleware exists in `backend/app/main.py`.
- **Impact:** confirms threat **T1 (fake SOS flooding)** with hard evidence rather than
  inference. Enables credential brute-forcing, incident flooding, and resource exhaustion.
- **Fix:** per-principal and per-IP limits (`slowapi` or a reverse-proxy limit), with
  tighter limits on `POST /v1/incidents` and any authentication path.
- **Verification:** 100 requests in 10 s must yield at least one `429`.

### QA-004 · No security response headers
- **Severity:** P2 · **Category:** Security misconfiguration · **Status:** Verified · **Confidence:** High
- **Evidence:** `curl -si localhost:8000/health` returns only `date`, `server`,
  `content-length`, `content-type`. Missing: `x-content-type-options`,
  `strict-transport-security`, `x-frame-options`, `referrer-policy`,
  `content-security-policy`, `permissions-policy`.
- **Impact:** lower for a JSON API than for an HTML app, but `nosniff` and HSTS are
  cheap and absent. `server: uvicorn` also discloses the stack unnecessarily.
- **Fix:** a small middleware setting `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, and HSTS behind TLS.

### QA-005 · Five npm vulnerabilities in the build toolchain (1 critical, 1 high)
- **Severity:** P2 · **Category:** Supply chain · **Status:** Verified · **Confidence:** High
- **Evidence:** `npm audit` — critical `vitest` (GHSA-5xrq-8626-4rwp, arbitrary file
  read/exec when the Vitest UI server listens), high `vite` (GHSA-4w7w-66w2-5vf9 path
  traversal; GHSA-fx2h-pf6j-xcff `server.fs.deny` bypass), moderate `esbuild`
  (GHSA-67mh-4wv8-2f99 — any website can read dev-server responses), `@vitest/mocker`,
  `vite-node`.
- **Mitigating fact:** `npm audit --omit=dev` reports **0 vulnerabilities**. All five are
  developer-tooling only; the shipped bundle (`react`, `react-dom`,
  `@tanstack/react-query`, `zod`) is clean.
- **Impact:** a developer running `make run-dashboard` on an untrusted network is exposed.
- **Fix:** `npm audit fix` (upgrades available and non-breaking for vite 6 → 7 majors
  should be checked). Not applied — this audit does not modify files.

### QA-006 · Silent drop of malformed attachment chunks
- **Severity:** P2 · **Category:** Reliability / Observability · **Status:** Verified · **Confidence:** High
- **Evidence:** `protocol/dms/node.py:562`
  ```python
  try:
      session.receive_chunk(int(doc["index"]), bytes.fromhex(doc["data"]))
  except Exception:
      return
  ```
- **Impact:** a malformed or corrupt chunk is discarded with **no audit entry and no
  counter**. The attachment silently never completes and nothing explains why. This is
  the same failure shape as ADR-0003 (delivery recorded on send) — a loss that announces
  nothing. Neighbouring handlers in the same function *do* emit `ATTACHMENT_REJECTED`
  and `ATTACHMENT_FAILED`, so this is an inconsistency, not a considered choice.
- **Fix:** catch `(ValueError, KeyError, TransferError)` specifically and
  `self.audit("ATTACHMENT_CHUNK_REJECTED", ...)`.
- **Verification:** feed a chunk with odd-length hex; assert an audit entry appears.

### QA-007 · No test coverage measurement
- **Severity:** P2 · **Category:** Test quality · **Status:** Verified · **Confidence:** High
- **Evidence:** `import coverage` and `import pytest_cov` both fail; no coverage
  configuration in `pytest.ini` or `ruff.toml`.
- **Impact:** 395 tests is a count, not a coverage claim. No document should imply
  otherwise, and none currently does — but untested branches are invisible.
- **Fix:** add `pytest-cov`, run `--cov=dms --cov-report=term-missing`, set a floor in CI.

### QA-008 · No reduced-motion support
- **Severity:** P2 · **Category:** Accessibility (WCAG 2.3.3) · **Status:** Verified · **Confidence:** High
- **Evidence:** `grep -c prefers-reduced-motion dashboard/src/styles/app.css` → `0`.
- **Impact:** users with vestibular sensitivity get no relief. Currently low-harm — the
  UI has few transitions — but the guard should exist before any are added.
- **Fix:** `@media (prefers-reduced-motion: reduce) { *, ::before, ::after {
  animation-duration: .01ms !important; transition-duration: .01ms !important; } }`

### QA-009 · AI service accepts unbounded nested JSON
- **Severity:** P2 · **Category:** Input validation · **Status:** Verified · **Confidence:** Medium
- **Evidence:** `POST /v1/summarize` with a 400-deep nested incident returned `200`.
  It did not crash — the summariser reads scalar fields — but nothing bounds the input.
- **Impact:** same class as QA-001, currently without the same consequence. Parsing cost
  is unbounded.
- **Fix:** type `SummarizeRequest.incidents` properly rather than `list[dict[str, Any]]`.

### QA-010 · `access-control-allow-credentials` returned to disallowed origins
- **Severity:** P3 · **Category:** Security misconfiguration · **Status:** Verified · **Confidence:** High
- **Evidence:** `curl -si -H "Origin: https://evil.example" /health` returns
  `access-control-allow-credentials: true` with **no** `access-control-allow-origin`.
- **Impact:** none exploitable — without `ACAO` the browser blocks the response. Untidy.

### QA-011 · No form labels in the dashboard
- **Severity:** P3 · **Category:** Accessibility · **Status:** Verified (latent) · **Confidence:** High
- **Evidence:** `<label>` count is 0; `<input>` count is 0. There are no forms yet, so
  there is no current defect — but the pattern is unestablished for when one is added.

### QA-012 · No code splitting; single 247 KB bundle
- **Severity:** P3 · **Category:** Performance · **Status:** Verified · **Confidence:** High
- **Evidence:** `dist/assets/index-*.js` = 246.8 KB (75 KB gzipped), single chunk.
- **Impact:** acceptable for a desktop operations console; poor on a degraded network,
  which is precisely this product's context.

---

## 3. Verified checks that passed

| Check | Evidence |
|---|---|
| SQL injection | `Robert'); DROP TABLE incidents;--` stored verbatim; table intact, 6 incidents still queryable. Parameterized queries throughout. |
| Cross-tenant isolation | Other-org `GET`, `acknowledge`, `PATCH status` on a victim incident all returned `404` (not 403 — does not confirm existence). |
| Mass assignment | Body-supplied `organization_id: org_other`, `is_admin: true`, `revision: 99` had no effect — stored org was `org_demo` (from the principal), `is_admin` not persisted. |
| Malformed input | Broken JSON, empty body, bare array, `null`, wrong types → all `422`. |
| Oversized body | 9.6 MB payload → `422`. |
| Auth bypass | Empty, blank, Basic, and trailing-token headers → `401`. Lowercase `bearer` accepted (correct per RFC 7235). |
| Verb tampering | `PUT/DELETE/PATCH/TRACE/OPTIONS` on a GET route → `405`. |
| Error leakage | Zero stack traces in responses; structured `{error, detail}` envelope throughout. |
| Log hygiene | Zero occurrences of incident text in the gateway log across the whole session. |
| XSS sinks | No `dangerouslySetInnerHTML`, `innerHTML`, or `eval` in `dashboard/src`. |
| Mesh resilience to QA-001 | `_incident_from_doc` discards the nesting and re-serializes cleanly — verified by direct test. |
| Dead code markers | 0 TODO/FIXME/HACK/XXX across all sources. |
| Disabled tests | 1 skip, justified (Kotlin engine absent), no `.only()`, no `xfail`. |

---

## 4. Blocked checks

| Check | Reason | Command to run later |
|---|---|---|
| Browser / E2E QA (Prompt 05) | No Playwright or Puppeteer | `npx playwright test` after `npm i -D @playwright/test` |
| Automated a11y scan (Prompt 06) | No axe-core runner | `npx @axe-core/cli http://localhost:5173` |
| Viewport matrix (Prompt 04) | Requires a browser | Playwright device emulation |
| Container audit (Prompt 14) | Docker not installed | `docker build -f backend/Dockerfile .` then `trivy image` |
| SAST | No bandit/semgrep | `bandit -r protocol backend ai-service` |
| Android build & tests | No Android SDK, no Gradle, JDK 25 > AGP support | `./gradlew testDebugUnitTest` on a configured machine |
| Coverage percentage | No pytest-cov | `pytest --cov=dms --cov-report=term-missing` |
| Load/perf baseline | No k6/locust | `k6 run` against a seeded gateway |

---

## 5. Top remediation priorities

| # | Finding | Action | Effort |
|---|---|---|---|
| 1 | QA-001 | Type `people_affected` / `conditions`; `extra="forbid"`; regression test | ~1 h |
| 2 | QA-003 | Add rate limiting to the gateway | ~2 h |
| 3 | QA-002 | Add `.github/workflows/ci.yml` with pinned actions | ~1 h |
| 4 | QA-006 | Audit the silent chunk drop | ~15 min |
| 5 | QA-005 | `npm audit fix`, re-run dashboard tests | ~30 min |
| 6 | QA-004 | Security-headers middleware | ~30 min |
| 7 | QA-007 | pytest-cov with a CI floor | ~30 min |
| 8 | QA-008 | reduced-motion media query | ~5 min |

---

## 6. Release gate

**Classification: HOLD RELEASE.**

QA-001 alone is disqualifying: a low-privilege user can persistently disable the
coordinator's operational view. QA-002 means no regression protection exists, and
QA-003 confirms an inference from the existing threat model with direct evidence.

The prior `RELEASE_BLOCKERS.md` list (14 items, Android and identity issuance) remains
open and is unchanged by this audit. This audit adds three new blockers that are
fixable in roughly half a day.

---

## 7. Suggested next audit

Prompt 05 (browser automation) and Prompt 06 (accessibility), after installing
Playwright and `@axe-core/cli` — that is the largest remaining evidence gap, since the
dashboard has never been exercised in a real browser.
