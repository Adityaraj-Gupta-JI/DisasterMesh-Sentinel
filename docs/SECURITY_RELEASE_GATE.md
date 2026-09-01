# Security and Privacy Release Gate

Conservative standard. A gate fails unless there is evidence it passes.

## Result: **PASS for demonstration · FAIL for deployment**

## Gate checks

| # | Condition that blocks release | Result | Evidence |
|---|---|---|---|
| 1 | Secrets committed to the repository | **PASS** | No credentials in source; `.env` git-ignored; `.env.example` holds placeholders. Development API keys are labelled and disabled under `DMS_ENV=production` |
| 2 | Sensitive data logged by default | **PASS** | Logs carry request id, path, status, timing only; `DMS_AI_LOG_PAYLOADS=false`; `test_relay_status_exposes_counts_but_no_content` |
| 3 | Unauthorized roles can access restricted incidents | **PASS** | `can_receive` + per-route permissions; 14 governance tests; org isolation returns 404 |
| 4 | Files committed before hash verification | **PASS** | Quarantine → digest check → atomic rename; `test_hash_mismatch_never_commits` |
| 5 | Public alerts issuable without authorization | **PASS** | `PUBLISH_ALERT` plus `confirm: true`; `test_only_authority_publishes_alerts` |
| 6 | AI can dispatch automatically | **PASS** | No code path exists; asserted by three tests |
| 7 | Expired bundles forwarded indefinitely | **PASS** | Expiry checked on send and receive; `test_expired_bundle_is_never_forwarded` |
| 8 | Migrations can destroy data without approval | **PASS** | Additive migrations only; Android Room has no destructive fallback |
| 9 | File uploads lack size and MIME validation | **PASS** | 8 MB cap, MIME allow-list, executables and archives refused |
| 10 | Test credentials usable in production paths | **PASS** | Production with no `DMS_API_KEYS` authorizes nobody; `/ready` warns when dev keys are active |

## Non-blocking findings

| Severity | Finding | Reference |
|---|---|---|
| High | Identity issuance is unauthenticated | T2, B5 |
| High | Pre-shared organisation key, no forward secrecy | B6 |
| High | Android transport never compiled or radio-tested | B1, B2 |
| Medium | No revocation distribution | T4, B7 |
| Medium | No rate limiting | T1, B9 |
| Medium | No data retention policy | A5, B10 |
| Low | Relay-visible metadata permits coarse inference | A8 |

## Manual verification checklist

- [ ] `grep -rn "password\|secret\|api_key" --include="*.py" --include="*.ts"` returns
      only configuration names, never values
- [ ] `.env` is absent from `git status`
- [ ] `/ready` warns when development keys are active
- [ ] A dispatch without `confirm=true` returns 400
- [ ] A relay's stored bundles contain no plaintext
- [ ] The audit ledger verifies after a full demo run

## Sign-off

Passed for demonstration only, by the project's own adversarial test suite. **No
external security review has taken place.** See RELEASE_BLOCKERS.md.
