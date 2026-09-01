# Security Model

What is protected, from whom, and by what. Implemented in `protocol/dms/crypto/` and
`protocol/dms/governance/`; tested in `test_crypto.py` and `test_governance.py`.

## The central assumption

**The relay is untrusted.** A volunteer's phone carrying someone else's emergency
report is the normal case, not an edge case. Everything follows from that: the payload
is encrypted end to end, the header is signed by the originator, and the relay is given
exactly the metadata it needs to route and nothing more.

Carrying is not reading. `can_receive()` decides what a node may be *offered*;
`can_read_plaintext()` decides what it may *open*. A relay passes the first and fails
the second, and the test suite asserts both.

## Cryptography

| Concern | Choice | Why |
|---|---|---|
| Payload confidentiality | AES-256-GCM | Authenticated encryption: tampering fails decryption rather than producing plausible garbage. |
| AAD | The bundle id | Binds ciphertext to its header; a payload cannot be moved onto another bundle. |
| Nonce | 12 random bytes per encryption, tracked for reuse | GCM nonce reuse under one key is catastrophic; a test asserts 50 encryptions produce 50 distinct nonces. |
| Header integrity | Ed25519 over the canonical signable subset | Fast to verify on a phone; deterministic signatures. |
| File integrity | SHA-256 whole-file, verified in quarantine | A file is committed only after its digest matches. |
| Audit integrity | SHA-256 hash chain | Any edit, deletion, or reordering breaks the chain. |

### What the signature deliberately excludes

`hop_count`, `replication_count`, and `path` — the fields relays must update. Including
them would force re-signing at every hop, which would mean either relays hold signing
authority over content, or the chain of custody breaks. Excluding them means a relay
can route but cannot rewrite.

## Key handling

- Ed25519 signing keys are generated per node. On Android the same interface is served
  by the platform Keystore (written, not yet compiled).
- The organisation payload key is a **pre-shared symmetric key**. This is the weakest
  part of the design and is stated as such in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).
- `SoftwareKeyStore` is labelled `development_only` by default.
- Revocation is checked inside signature verification: a revoked node's signatures stop
  verifying immediately, everywhere.

## Authorization

Seven roles, ten permissions, one decision function. The full matrix is in
`ROLE_PERMISSIONS`; the properties that matter:

| Rule | Enforced by |
|---|---|
| A citizen cannot dispatch | `require(ASSIGN_RESOURCE)` — API returns 403 |
| A relay cannot read restricted content | `can_read_plaintext()` returns False; it also lacks the key |
| Only a government authority can publish an alert | `require(PUBLISH_ALERT)` |
| A revoked or expired credential receives nothing | `can_receive()` first check |
| Exact location is restricted | coarsened to ~1 km without `VIEW_PRECISE_LOCATION` |
| Organisations are isolated | every gateway query is scoped; cross-org access returns **404, not 403**, so the API does not confirm another organisation's records exist |

A coordinator *does* hold `VIEW_MEDICAL_DATA` — see ADR-0002. Withholding triage detail
from the person deciding whether to send the ambulance would break the product, not
protect the patient.

## The human gates

Three actions can never happen automatically, at any confidence:

1. **Dispatch** — requires `ASSIGN_RESOURCE` *and* an explicit `confirm=true`. The API
   returns `confirmation_required` otherwise, and the UI puts the word "simulated" in
   the confirmation dialog.
2. **Public alert** — requires `PUBLISH_ALERT` *and* `confirm: true` in the body.
3. **Closing an incident** — requires `CLOSE_INCIDENT`.

No AI output reaches any of these paths. The priority engine cannot dispatch; the
summariser returns "coordinator to decide dispatch"; the model registry labels every
response `recommendation_only`.

## Data handling

- Original user input is never overwritten. Translations and transcripts are separate
  records marked `machine_generated`.
- Attachments land in quarantine, are verified, then atomically renamed into place with
  mode `0600`. Received files are never executed; executables and archives are refused
  by MIME policy.
- Logs carry request ids, paths, and timings — never payload text. `DMS_AI_LOG_PAYLOADS`
  defaults to false.
- Android cloud backup and device transfer exclude the database and attachments.

## Production posture

`DMS_ENV=production` with no `DMS_API_KEYS` configured authorizes **nobody** — the
service fails closed rather than falling back to development keys. `/ready` reports
loudly when development keys are active. CORS is an explicit allow-list, never `*`.

## What has not been done

No external security review, no penetration test, no fuzzing of the Kotlin code, and no
cryptographic review. See [THREAT_MODEL.md](THREAT_MODEL.md) for the attacks considered
and the ones still unmitigated.
