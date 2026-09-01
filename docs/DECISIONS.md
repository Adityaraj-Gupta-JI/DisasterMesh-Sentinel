# Architecture Decision Records

One entry per significant trade-off. Append; never rewrite history. Required before
any change to a shared contract (domain model, DMBP schema, API surface, crypto).

Template:

```
## ADR-NNN — Title
Date: YYYY-MM-DD · Status: Proposed | Accepted | Superseded by ADR-NNN
### Context
### Decision
### Consequences
### Alternatives considered
```

---

## ADR-001 — Mock-first, contract-first construction order
Date: 2026-08-31 · Status: Accepted

### Context
The system's riskiest parts (Nearby Connections radio behavior, real ML models,
physical multi-device relay) are exactly the parts that cannot be tested in the
development environment. Building against them first would make every downstream
module unverifiable.

### Decision
Build in this order: domain contracts → mock offline flow → persistence → protocol →
sync engine → UI → real transport → AI → governance → dispatch → audit. Every
external dependency (transport, AI, crypto) gets an interface plus a deterministic
mock implementation before any real adapter.

### Consequences
- The whole critical path is testable on a laptop with no phones and no models.
- Mock success must never be reported as real success; status docs must distinguish them.
- Slight upfront cost in interface design.

### Alternatives considered
Device-first development — rejected: untestable here, and it would let transport
details leak into the domain model.

---

## ADR-002 — AI proposes, deterministic policy decides
Date: 2026-08-31 · Status: Accepted

### Context
Priority determines whether a life-threatening report is delivered first. Model
output is non-deterministic, degrades on out-of-distribution and code-switched
input, and may be unavailable entirely.

### Decision
The priority engine is deterministic and rule-based. It consumes a normalized AI
result as one input among many and applies hard escalation rules that AI uncertainty
cannot silently downgrade. With AI absent or failing, rules alone produce a priority.
No module may dispatch or publish an alert from a model output.

### Consequences
- Priority is reproducible for the same inputs and policy version, and explainable.
- Requires a versioned policy attached to every decision record.
- Some nuance a model could catch is lost — acceptable for a safety-critical path.

### Alternatives considered
Direct model-score-to-priority mapping — rejected: unexplainable, non-reproducible,
and it fails closed to nothing when the model is unavailable.

---

# Architecture Decision Records — implementation phase

## ADR-0002 · Coordinators may read medical content

**Status** Accepted · 2026-08-31

**Context** The permission matrix initially withheld `VIEW_MEDICAL_DATA` from
`EVENT_COORDINATOR`, on the reasoning that medical detail should be seen by medics
only. That contradicted the priority engine, which routes medical P0 incidents to
coordinators — and it broke the core MVP flow: a coordinator who cannot see that a
patient is unconscious cannot sensibly decide to send the ambulance. The contradiction
surfaced as a scheduler test where a coordinator was refused their own incident.

**Decision** `EVENT_COORDINATOR` holds `VIEW_MEDICAL_DATA`. `VOLUNTEER_RELAY` does not,
and never will: it carries ciphertext and lacks the key.

**Consequences** Triage detail is visible to the role that acts on it. The
carry-versus-read boundary now sits exactly where the encryption boundary sits, which
is easier to reason about than a third intermediate tier. A future deployment with
stricter rules can withhold the organisation key from coordinators without any code
change.

## ADR-0003 · Delivery is recorded on receipt, not on send

**Status** Accepted · 2026-08-31

**Context** The sync engine marked a bundle delivered at the moment it was sent. The
file-interruption simulator scenario then failed: after a link dropped mid-transfer,
the sender believed the receiver had the bundle and never re-offered it. The report was
silently lost — the worst possible failure for this product.

**Decision** `mark_delivered` is called only when a `BUNDLE_RECEIPT` arrives.

**Consequences** Interrupted transfers resume on the next contact. A small amount of
redundant offering is possible if a receipt is lost, which deduplication absorbs
harmlessly. Optimism about delivery is not an acceptable trade in this domain.

## ADR-0004 · No dependency-injection framework on Android

**Status** Accepted · 2026-08-31

**Context** The prompt pack suggested Hilt. The Android graph is small: a database, a
transport, a keystore, and a sync engine.

**Decision** A hand-written container in `SentinelApplication`.

**Consequences** One readable file instead of a plugin, an annotation processor, and
generated code. If the graph grows past roughly a dozen bindings, revisit.

## ADR-0005 · Proximity modulates similarity, it never creates it

**Status** Accepted · 2026-08-31

**Context** Clustering initially summed semantic, temporal, geographic, and categorical
signals. Two unrelated reports made at the same place five minutes apart — a fire and a
water request — scored high enough to be LINKed, because in a disaster *everything* is
close in time and space.

**Decision** Content decides (`0.60 × semantic + 0.40 × categorical`); proximity only
scales that judgement (`0.50 + 0.25 × temporal + 0.25 × geographic`).

**Consequences** Two reports of one collapse still merge; a fire and a water request at
the same corner stay separate. Clustering is also honest about missing location rather
than treating absence as agreement.

## ADR-0006 · The gateway stores the canonical domain document

**Status** Accepted · 2026-08-31

**Context** The gateway initially persisted its own API-shaped document. Two defects
followed: location redaction never fired, because the redactor looked for a nested
`location` object that the flat API payload did not have — meaning precise coordinates
were served to callers without `VIEW_PRECISE_LOCATION`; and cluster rebuilding silently
skipped every incident because the domain parser could not read the shape.

**Decision** The gateway stores exactly `Incident.to_dict()`. Cluster rebuilding now
reports unreadable documents in its response rather than swallowing them.

**Consequences** One document shape across phone, gateway, and dashboard. A privacy
control that silently did nothing now works, and a parser that silently skipped
everything now says so.

## ADR-0007 · The rule engine is the fallback and the mock

**Status** Accepted · 2026-08-31

**Context** A mock that behaves unlike the fallback would mean tests prove nothing
about degraded operation — which is the operating mode this product exists for.

**Decision** `dms/ai/rules.py` is both the development mock and the on-device fallback
when no model is reachable.

**Consequences** Every test exercises the real offline path. The rule engine must
therefore stay genuinely correct rather than merely plausible, which is why it carries
multilingual lexicon tests of its own.

## ADR-0008 · The bundle path records the route travelled

**Status** Accepted · 2026-08-31

**Context** `forwarded()` appended the sending node, so a two-hop delivery produced
`A → A → B` — technically a record of who forwarded, but unreadable as a route.

**Decision** Forwarding appends the receiving node, giving `A → B → C`.

**Consequences** A coordinator can read the chain of custody directly. Combined with
the signed header, the path shows which devices carried a report without letting any of
them alter what it says.

## ADR-0009 · One frozen contract governs both priority engines

**Status** Accepted · 2026-08-31

**Context** The priority engine is implemented twice: Python in `protocol/` and Kotlin
in `android-app/`. Their unit tests mirrored each other, which reads like safety but is
not: two suites can be edited together, and nothing mechanical stopped the engines
diverging. A divergence would mean a phone and the gateway ranking the same emergency
differently — and nothing would report it. The Android module cannot even be compiled
here, so the Kotlin side had no executed test at all.

**Decision** A single frozen file, `test-fixtures/priority-engine-contract.json`, holds
37 input/output cases generated from the Python reference. Both test suites read it, so
whichever engine changes, its own test fails. Because the Kotlin suite cannot run
without an SDK, a third test — `test_engine_parity.py` — reads the Kotlin *source* and
compares its rule tables, thresholds, escalation strings, coefficients, and policy
version against Python's.

The contract records values only. Explanation prose differs between the languages by
design; what must not differ is the decision.

**Consequences** Drift now fails a test today rather than after the Android module
first compiles. Verified by mutation: four realistic divergences — a lowered P0
threshold, a dropped life-threat condition, a changed trapped-person floor, a shortened
P0 TTL — each fail a named test with a message naming the difference.

The parity check compares tables and coefficients, not control flow, so it is a smoke
alarm rather than a fire door. Running `PriorityContractTest` remains necessary and is
tracked as release blocker B3. Regenerating the contract is deliberate (`make
contract`); the diff is the review, and a changed expected score has to be justified
rather than absorbed.

## ADR-0010 — Multi-hop simulation reuses the mesh stack; live view is polled, not pushed
Date: 2026-09-01 · Status: Accepted
### Context
We needed to simulate and watch arbitrary N-hop delivery, not just the fixed
reporter→relay→coordinator line, and to see hops live in the coordinator dashboard.
The mock radio already supports any link graph, bundles already carry `hop_count`
and `path`, and the dashboard already polls the gateway every 5s.
### Decision
Build the multi-hop driver inside `protocol/dms/sim/` on top of the existing `Mesh`,
`MockRadio`, and node stack — no new top-level package, no new routing code. The
driver emits one ordered `MeshEvent` stream (topology, hops, delivery, quiescence);
the terminal view, an in-memory gateway ring buffer, and the dashboard are all just
renderers of that stream. The dashboard reads it by polling `/v1/mesh/runs/{id}/events?since=`
(a monotonic cursor), matching the existing React-Query pattern, rather than a WebSocket.
### Consequences
- Hops are measured from the protocol's own `hop_count`/`path`, never re-derived.
- Runs are ephemeral and in-memory; they vanish on gateway restart, like the mesh itself.
- A ~700ms poll shows near-real-time hops without new transport machinery or a socket to manage.
- The six-hop DMBP `hop_limit` is a real ceiling: chains longer than seven nodes do not
  deliver end to end, and a test asserts this rather than treating it as a bug.
### Alternatives considered
- A separate simulation project: rejected — it would re-import or duplicate the whole stack.
- WebSocket streaming: deferred — more plumbing than the 5s-poll dashboard needs today.
- Explicit routing tables: rejected — a disaster mesh is store-carry-forward gossip, not routed.

## ADR-0011 — Image bytes and audio transcription are additive, hung off the existing flows
Date: 2026-09-01 · Status: Accepted
### Context
Coordinators saw a placeholder box instead of photo evidence, and there was no way to
send an image or a voice note from the dashboard. The mesh already transfers image
chunks, the gateway already stored attachment *metadata*, and the AI service already
exposes `/v1/transcribe` and a priority engine. The requirement was to extend, not
rewrite: keep the text-message flow exactly as it is.
### Decision
- **Image render bug:** root cause was that attachment bytes were never stored or
  served — only metadata. Fixed structurally by adding a nullable `attachments.data`
  column (with an additive `ALTER TABLE` for existing databases), storing bytes only
  when a caller supplies them, verifying size + sha256, and serving them from a new
  `GET …/attachments/{id}/content` endpoint. The dashboard fetches the bytes as an
  authenticated blob and renders a real `<img>`.
- **Audio:** a new `POST /v1/transcribe` wraps the existing speech-to-text mock; the
  transcript is sent through a new `POST /v1/compose` that classifies with the same
  triage + priority engine a device uses and then calls the existing `create_incident`
  verbatim. Audio → text → the ordinary incident pipeline; no parallel message system.
- Everything is behind new endpoints, new schema fields (all optional), and new UI
  tabs/components. No existing endpoint, schema, or flow was modified.
### Consequences
- Metadata-only attachments and every existing caller keep working unchanged; bytes
  are opt-in via `data_base64`.
- A transcribed voice note is indistinguishable from a typed report downstream —
  storage, clustering, dispatch, and display all apply with zero new code paths.
- Android received the same features (picker, Coil rendering, transcribe→report) but
  **cannot be compiled or verified here**; those changes are additive and unverified.
### Alternatives considered
- Serving image bytes via a query-param token so a bare `<img src>` works: rejected —
  it would weaken the auth model; the authenticated-blob fetch keeps scoping intact.
- Duplicating incident creation inside `/v1/compose`: rejected — it calls the existing
  `create_incident` so there is one persistence path, not two.
