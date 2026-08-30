# Contributing

## Before you start

Read `CLAUDE.md`. Then read `docs/DEVELOPMENT_STATUS.md` to learn what actually
exists — do not infer status from directory names.

## Loop

1. Pick the smallest slice that satisfies one acceptance criterion.
2. Write the test alongside the implementation, not after the fact.
3. `make lint && make fmt` (Python), plus the narrowest relevant test target.
4. Review your own diff before reporting.
5. Update `docs/DEVELOPMENT_STATUS.md`.
6. Add an ADR to `docs/DECISIONS.md` for any shared-contract or trade-off decision.

## Commits

`<area>: <imperative summary>` — e.g. `protocol: reject bundles past expiry`.
Areas: `protocol`, `backend`, `ai`, `android`, `dashboard`, `docs`, `tests`, `repo`.
One logical change per commit. Never commit `.env`, keystores, or model weights.

## Reporting

```
## Status
## Changes
## Verification
## Known limitations
## Next action
```

State honestly which parts are mocked, which are hardware-dependent, and which are
untested. "It compiles" is not verification.

## Hard rules

- No new dependency without justification in the report.
- No test deleted or weakened to make a check pass.
- No security check disabled.
- No real emergency service contacted, ever.
- Original user input, hashes, timestamps, and provenance are always preserved.
