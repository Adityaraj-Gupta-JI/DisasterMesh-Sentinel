# Architecture Review

A release-readiness review of the code as built, conducted against the invariants in
CLAUDE.md. Severity is stated first; nothing is softened.

## Verdict

**Fit for a hackathon MVP demonstration. Not fit for deployment.** The safety
properties that matter are structural rather than aspirational, and they are tested.
The gaps are concentrated in identity, key management, and the unbuilt Android module.

## Strengths

**The AI cannot act.** There is no code path from inference to dispatch. The priority
engine takes typed fields and cannot reach the dispatch service; the dispatch service
requires an explicit human actor and role; the API requires `confirm=true`. Three
independent tests assert this from three directions. This is the property the whole
product exists to guarantee, and it is enforced by structure, not discipline.

**Boundaries are load-bearing.** Transport is abstracted well enough that the complete
sync path — inventory exchange, scheduling, authorization, chunked transfer, resume — is
tested with no radio at all. That is why the Android gap costs radio verification only,
not product verification.

**Degraded modes are the tested path, not an afterthought.** The rule engine is both the
development mock and the on-device fallback (ADR-0007), so every test exercises the
offline behaviour the product is designed around.

**Decisions are explained, and the explanation travels.** Priority scores carry a
line-by-line trace; scheduler verdicts carry a reason and policy version; dispatch
recommendations carry a rationale. A coordinator can always ask "why" and get an answer.

## Weaknesses

**Severity: high — identity issuance is unauthenticated.** Anyone can mint a node
keypair. Sybil resistance (T2), rate limiting (T1), and revocation distribution (T4) all
depend on fixing this. It is the single highest-value next piece of work.

**Severity: high — the payload key is pre-shared.** No key exchange, no per-incident
keys, no forward secrecy. Compromise of one organisation key exposes every bundle
encrypted under it.

**Severity: high — the Android module is unverified.** 2,224 lines that have never met a
compiler, including the only real transport implementation.

**Severity: medium — inventory exchange sends exact id lists.** Fine at demo scale,
quadratic in conversation size as bundles accumulate. The `InventoryDigest` interface
exists precisely so a Bloom filter can replace it, but none is written.

**Severity: medium — multi-hop delivery needs several exchange rounds** because a relay
only re-offers what it has already received. Correct, but chatty.

**Severity: low — the dashboard polls** every five seconds instead of using WebSocket or
SSE. Acceptable for a demo; wasteful for a long shift.

## Coupling

`MeshNode` is the only component that knows about all the others, which is the intended
shape for a composition root. It is around 600 lines and is the file most likely to grow
badly; if it passes roughly 800, the reporting, receiving, and coordination
responsibilities should be split behind their own interfaces.

The gateway duplicates some domain logic (lifecycle checks, capability matching) rather
than importing it. That duplication is currently thin and tested on both sides, but it
is a real drift risk and should be consolidated before either grows.

## Observability

Good within a node: scheduler decisions, audit ledger, sync statistics. Weak across
nodes — there is no way to ask "where is incident X right now" other than inspecting the
`path` on bundles that have arrived. For a mesh, that is a genuine operational gap.

## Testing

395 tests, fast (~4s), deterministic (fixed clock, mock transport, rule AI). Property
and fuzz tests cover the protocol and scheduler. The notable gaps: no browser test, no
Android test execution, no load test above three nodes, and no chaos testing of
concurrent exchanges.

## Recommendation

Ship the demo. Before anything further, in order: compile Android, run a two-device
radio test, implement identity issuance, then replace the pre-shared key.
