# Release Blockers

What must be true before this is deployed anywhere real. Everything here is currently
**unmet** — this is a hackathon MVP.

## Blocking — safety

| # | Blocker | Status |
|---|---|---|
| B1 | Android module compiles and passes its unit tests | **UNMET** — never compiled |
| B2 | Two-device Nearby Connections test passes | **UNMET** — no hardware |
| B3 | Kotlin and Python priority engines proven equivalent by a shared fixture | **PARTLY MET** — the shared contract exists and both suites read it; source-level parity is enforced today, but the Kotlin conformance test cannot run until B1 |
| B4 | An unacknowledged P0 cannot be silently evicted when storage fills | **UNMET** — no eviction policy (T14) |

## Blocking — security

| # | Blocker | Status |
|---|---|---|
| B5 | Authenticated identity issuance | **UNMET** — anyone can mint a keypair |
| B6 | Key exchange replacing the pre-shared organisation key | **UNMET** |
| B7 | Revocation list distribution | **UNMET** — revocation is local only |
| B8 | External security review of the cryptographic design | **UNMET** |
| B9 | Rate limiting per node | **UNMET** (T1) |
| B10 | Data retention policy for incident content and audit entries | **UNMET** (A5) |

## Blocking — operational

| # | Blocker | Status |
|---|---|---|
| B11 | Load testing beyond three nodes | **UNMET** |
| B12 | Docker stack actually run | **UNMET** — docker unavailable here |
| B13 | Dashboard exercised in a browser against a live gateway | **UNMET** |
| B14 | Backup and restore procedure for the gateway | **UNMET** |

## Not blocking for a demo

Real ML models, map view, push notifications, federation, responder app. Each is absent
by choice and recorded in KNOWN_LIMITATIONS.

## Statement

This prototype must not be used in an actual emergency. Fourteen release blockers are
open, four of them safety-critical.
