# Security Review

Adversarial review of the implementation. The full attack catalogue is in
[THREAT_MODEL.md](THREAT_MODEL.md); misuse by authorized users is in
[ABUSE_CASES.md](ABUSE_CASES.md). This document records what the review actually found.

## Method

Static review of every module against the CLAUDE.md invariants, plus adversarial tests
written to break them: fuzzed protocol frames, mutated headers, truncated wire data,
tampered ledgers, wrong keys, revoked identities, unauthorized receivers, oversized and
executable attachments, and replayed bundles.

## Findings from the review

**F1 — Contradictory authorization (fixed).** The permission matrix denied coordinators
medical access while the priority engine routed medical incidents to them. Found by a
scheduler test. Resolved in ADR-0002.

**F2 — Silent data loss on interrupted transfer (fixed).** Delivery was recorded on
send, so an interrupted transfer was never re-offered. Found by simulator scenario 8.
Resolved in ADR-0003. This was the most serious defect found: an emergency report could
be lost with no error anywhere.

**F3 — Location redaction that never fired (fixed).** The gateway stored a flat
document while the redactor looked for a nested `location`, so precise coordinates were
served to callers lacking `VIEW_PRECISE_LOCATION`. Found by an API test. Resolved in
ADR-0006. A privacy control that silently does nothing is worse than none, because it is
trusted.

**F4 — Silent parser failure (fixed).** Cluster rebuilding swallowed every unparseable
document, so a total failure looked like "no duplicates found". It now reports
unreadable documents in its response.

**F5 — People-count extraction bound to the wrong number (fixed).** "Three people
trapped, one bleeding" extracted 1, because dictionary order beat text order. Numbers
are now bound to nearby people-nouns. In triage, an undercount is a dispatch error.

**F6 — Proximity manufacturing similarity (fixed).** Clustering summed temporal and
geographic closeness, so two unrelated reports at one street corner linked. In a
disaster everything is close. Resolved in ADR-0005.

## What was checked and found sound

- Nonce uniqueness under a single key (50/50 distinct across a test).
- Signature scope: mutable relay fields are excluded, so relays route without rewriting.
- Tamper, deletion, and reorder detection on the audit chain.
- Fuzzing: 500 random frames, 400 mutated headers, and every truncation of a valid frame
  produce domain errors, never a crash.
- Cross-organisation isolation, including the id-collision case.
- No path from model output to any action.

## Residual risk

Unauthenticated identity issuance and the pre-shared payload key. Both are documented,
neither is fixed, and together they account for most of what the threat model leaves
open. See [RELEASE_BLOCKERS.md](RELEASE_BLOCKERS.md).

## Reviewer's note

Six real defects were found, and three of them — F2, F3, F5 — were failures that
produced *no error at all*: a lost report, a privacy control that did nothing, and a
wrong count. Those are the failures this domain should fear most, because nothing
announces them. The simulator and the property tests earned their place by finding them.
