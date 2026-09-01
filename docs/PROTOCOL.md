# DisasterMesh Bundle Protocol (DMBP v1)

Transport-independent store-and-forward for emergency data. Implemented in
`protocol/dms/protocol/`, conformance-tested in `protocol/tests/test_protocol.py`.

## Why a bundle protocol

The link between two phones in a disaster is brief, unreliable, and unrepeatable. A
protocol that assumes a session will fail. DMBP assumes the opposite: each bundle is a
self-contained, self-describing, independently verifiable unit that any node can carry
without understanding it, and any node can validate without asking anyone.

## Wire format

```
┌────────────────┬──────────────────────────┬──────────────────────┐
│ length  (4 B)  │ canonical header JSON    │ payload (ciphertext) │
│ big-endian u32 │ sorted keys, no spaces   │ AES-256-GCM          │
└────────────────┴──────────────────────────┴──────────────────────┘
```

The header is canonically serialised — sorted keys, compact separators, UTF-8 — so a
hash or signature computed on one device reproduces byte-for-byte on another.

## Header fields

| Field | Purpose |
|---|---|
| `protocol_version` | `dmbp/1`. Anything else fails closed. |
| `bundle_id`, `incident_id`, `source_node_id` | Identity and provenance. Immutable. |
| `payload_type` | TEXT · UPDATE · ATTACHMENT_MANIFEST · ATTACHMENT_CHUNK · ACK · DISPATCH · EVENT_LOG |
| `payload_size`, `payload_hash` | SHA-256 over the exact bytes carried. Immutable. |
| `priority_class`, `priority_score` | Scheduling inputs, set by the policy engine. |
| `created_at`, `expires_at` | TTL derived from priority: P0 6 h → P3 48 h. |
| `hop_limit` / `hop_count` | Monotonic. Never decreases. |
| `replication_limit` / `replication_count` | Bounds how widely one bundle spreads. |
| `role_scope`, `sensitivity`, `organization_id` | Who may be *offered* this bundle. |
| `path` | Route travelled: originator, then each receiving node (`A → B → C`). |
| `signature`, `signer_node_id` | Ed25519 over the signable header subset. |
| `encryption` | Algorithm, key id, nonce. AAD is the bundle id. |

### What the signature covers

Everything a receiver trusts — ids, payload hash, priority, expiry, scope, encryption
metadata — and deliberately **not** `hop_count`, `replication_count`, or `path`, which
relays legitimately update. A relay can advance a bundle without invalidating the
originator's signature, and cannot alter what the bundle says.

## The eight invariants

Each has a dedicated test:

1. **Bundle ids are immutable** — the header is a frozen dataclass; forwarding returns a copy.
2. **Payload hashes are immutable** — verified on every receive, before storage.
3. **Hop count never decreases** — `forwarded()` is the only mutation path and only increments.
4. **Expired bundles are never forwarded** — checked before every send and on every receive.
5. **A bundle cannot be accepted twice as new** — dedup on `bundle_id` at the store boundary.
6. **A corrupted payload is rejected** — size and digest checked before anything is stored.
7. **Unknown versions fail closed** — an unrecognised `protocol_version` raises, never guesses.
8. **Critical text is independent of attachments** — text, manifest, and chunks are separate
   bundles sharing only an `incident_id`. Losing the photo leaves the report fully valid.

## Inventory exchange

```
A --INVENTORY_REQUEST(digest of what A holds)--> B
A <--INVENTORY_RESPONSE(digest of B) + BUNDLE_OFFER[metadata]-- B
A --BUNDLE_ACCEPT(ids A lacks, text before media)--> B
A <--BUNDLE_DATA(frames, hop+1)-- B
A --BUNDLE_RECEIPT(stored / rejected)--> B
A --BUNDLE_OFFER(what B's digest shows it lacks)--> B
```

Offers carry **metadata only** — id, type, priority, size, sensitivity, expiry. A node
that listens to an exchange learns that an incident exists and how urgent it is, never
what it says. What gets offered is decided by the scheduler, so authorization and the
text-before-media rule are enforced in exactly one place.

Delivery is recorded when a **receipt arrives**, never on send. A transfer cut off
mid-flight is therefore re-offered on the next contact — the bug that the file-interruption
simulator scenario caught.

## Scheduling order

Within one exchange, objects are ordered by:

1. priority class (P0 → P3),
2. **payload rank** — text, ack, update, dispatch, event log, manifest, chunk,
3. expiry urgency (under 15 minutes to live is promoted),
4. priority score, then size, then attempt count.

Payload rank sits *above* priority score deliberately: within P0, the text of a report
outranks its own photograph. That is the entire text-first promise, expressed as one
line in a sort key.

## Extension points

- `InventoryDigest` is an interface. `ExactDigest` is the MVP implementation; a Bloom
  filter can replace it without touching the exchange.
- `PayloadType` is versioned with the protocol; adding a type requires a version bump.
- Transport is fully abstracted (`dms/transport/base.py`), so DMBP runs unchanged over
  Nearby Connections, a socket, or the in-memory mock.
