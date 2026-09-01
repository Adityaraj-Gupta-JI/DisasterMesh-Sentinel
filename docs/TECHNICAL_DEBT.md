# Technical Debt

Known compromises, why they were made, and what paying them back costs.

| # | Debt | Why it exists | Cost to fix | Priority |
|---|---|---|---|---|
| D1 | Exact-list inventory digest | Correct and simple at demo scale | ~1 day for a Bloom filter behind the existing interface | Medium |
| D2 | Gateway duplicates lifecycle and capability logic | The gateway does not import the mesh domain package for lifecycle checks | ~0.5 day to consolidate on the shared package | Medium |
| D3 | `MeshNode` is a large composition root | Everything it composes is independently tested, so it stayed convenient | ~1 day to split reporter/receiver/coordinator responsibilities | Low |
| D4 | Dashboard polls every 5s | Server-push was not needed for a demo | ~0.5 day for SSE | Low |
| D5 | Multi-round exchange for multi-hop delivery | A relay re-offers only after receiving | ~1 day to pipeline offers | Low |
| D6 | Attachment chunks are separate bundles | Reuses the bundle path for free; costs header overhead per chunk | ~1 day for a dedicated chunk frame | Low |
| D7 | Fixed 64 KB chunk size | Not measured against real radios | Needs hardware to tune | Blocked |
| D8 | Battery model is a constant times bytes | No hardware to measure against | Needs hardware | Blocked |
| ~~D9~~ | ~~No Kotlin/Python contract test~~ | **RESOLVED** — frozen contract in `test-fixtures/priority-engine-contract.json`, read by both suites, plus a source-level parity check that runs without a Kotlin compiler | — | done |
| D10 | Development API keys in source | Convenience; disabled in production by config | ~0.5 day for a seeded key store | Medium |

## D9, and how it was closed

The Kotlin and Python priority engines encode the same rules twice. Mirrored unit tests
did not prevent drift, because both suites can be edited together — and a drift means a
phone and the gateway disagree about how urgent the same emergency is.

Three pieces now stand in the way:

1. **A frozen contract** — `test-fixtures/priority-engine-contract.json`, 37 cases
   covering the decision surface, generated from the Python reference by
   `make contract`. Regenerating it produces a diff, and the diff is the review.
2. **Both suites read it** — `test_priority_contract.py` and `PriorityContractTest.kt`.
   Whichever engine changes, its own test fails against the shared file.
3. **A source-level parity check that runs today** — `test_engine_parity.py` compares
   the urgency table, TTLs, replication limits, class thresholds, life-threat and hazard
   sets, escalation rule strings, eight scoring coefficients, and the policy version by
   reading the Kotlin source. It exists because piece 2 cannot execute until the Android
   module compiles.

Verified by mutation: lowering the P0 threshold, dropping `UNCONSCIOUS` from the
life-threat set, changing the trapped-person floor, and shortening the P0 TTL on the
Kotlin side each fail a named test with a message that says what differs.

**What remains:** the parity check compares tables and coefficients, not control flow.
Only compiling and running `PriorityContractTest` proves the Kotlin engine *combines*
them identically. That is blocked on the Android SDK, and it is tracked as release
blocker B3.
