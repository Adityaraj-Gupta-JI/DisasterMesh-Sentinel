# Diagrams

Every diagram reflects the code as built. Simulated and unbuilt components are labelled.

## 1 · System context

```mermaid
flowchart LR
  R[Reporter phone] -- DMBP --> V[Volunteer relay]
  V -- DMBP --> C[Coordinator]
  C -. opportunistic .-> G[Gateway API]
  G --> D[Dashboard]
  G -. optional .-> AI[AI service]
  C --> X[Dispatch SIMULATED]
  style X stroke:#d32f2f,stroke-dasharray: 4 4
```

## 2 · Mobile components — NOT COMPILED

```mermaid
flowchart TD
  UI[Compose screens] --> VM[View models]
  VM --> REPO[Repositories]
  REPO --> ROOM[(Room)]
  REPO --> SYNC[Sync engine]
  SYNC --> SCHED[Scheduler]
  SYNC --> T[Transport interface]
  T --> NEARBY[Nearby adapter]
  T --> MOCK[Mock transport]
  SYNC --> CRYPTO[Keystore + sealing]
  VM --> PE[Priority engine]
  style NEARBY stroke-dasharray: 4 4
```

## 3 · DMBP exchange

```mermaid
sequenceDiagram
  participant A as Reporter A
  participant B as Relay B
  A->>B: INVENTORY_REQUEST(digest)
  B->>A: INVENTORY_RESPONSE(digest) + OFFERS(metadata only)
  A->>B: BUNDLE_ACCEPT(missing ids, text first)
  B->>A: BUNDLE_DATA(hop+1)
  A->>B: BUNDLE_RECEIPT(stored)
  Note over A,B: delivery is recorded on receipt, never on send
```

## 4 · File transfer state machine

```mermaid
stateDiagram-v2
  [*] --> OFFERED
  OFFERED --> ACCEPTED: policy + expiry OK
  ACCEPTED --> TRANSFERRING
  TRANSFERRING --> PAUSED
  TRANSFERRING --> INTERRUPTED: link lost
  PAUSED --> TRANSFERRING
  INTERRUPTED --> TRANSFERRING: resume missing chunks
  TRANSFERRING --> VERIFYING: all chunks present
  VERIFYING --> COMMITTED: digest matches
  VERIFYING --> FAILED: digest mismatch
  OFFERED --> EXPIRED
  COMMITTED --> [*]
```

## 5 · AI pipeline

```mermaid
flowchart LR
  AUD[Audio] --> W[transcribe]
  W --> TXT[Text]
  TXT --> TR[triage]
  TXT --> NER[entities]
  TR --> PE[Priority engine]
  NER --> PE
  PE --> OUT[Score + class + explanation]
  PE -.never.-> DSP[Dispatch]
  HUM[Human] --> DSP
  style DSP stroke:#d32f2f
```

## 6 · Incident lifecycle

```mermaid
stateDiagram-v2
  [*] --> DRAFT
  DRAFT --> QUEUED
  QUEUED --> RELAYED
  QUEUED --> RECEIVED
  RELAYED --> RECEIVED
  RECEIVED --> ACKNOWLEDGED
  ACKNOWLEDGED --> DISPATCH_REQUESTED
  DISPATCH_REQUESTED --> DISPATCHED
  DISPATCHED --> EN_ROUTE
  EN_ROUTE --> ARRIVED
  ARRIVED --> RESOLVED
  QUEUED --> EXPIRED
  EXPIRED --> ACKNOWLEDGED: expiry hides, never erases
  RESOLVED --> [*]
```

## 7 · Dispatch lifecycle — all simulated

```mermaid
stateDiagram-v2
  [*] --> RECOMMENDED
  RECOMMENDED --> ASSIGNED: HUMAN authorization required
  ASSIGNED --> ACKNOWLEDGED
  ACKNOWLEDGED --> EN_ROUTE
  EN_ROUTE --> ARRIVED
  ARRIVED --> COMPLETED
  RECOMMENDED --> CANCELLED
  ASSIGNED --> CANCELLED
  COMPLETED --> [*]
```

## 8 · Governance

```mermaid
flowchart TD
  OBJ[Sync object] --> AUTH{can_receive?}
  AUTH -- no --> REJ[Rejected with a reason]
  AUTH -- yes --> OFFER[Offered]
  OFFER --> READ{can_read_plaintext?}
  READ -- no --> CARRY[Carried as ciphertext]
  READ -- yes --> KEY{holds org key?}
  KEY -- no --> CARRY
  KEY -- yes --> PLAIN[Readable]
```

## 9 · Offline to gateway

```mermaid
sequenceDiagram
  participant P as Phone
  participant G as Gateway
  Note over P: hours offline, bundles queue locally
  P->>G: POST /v1/sync/push (idempotent)
  G-->>P: accepted / deduplicated
  P->>G: GET /v1/sync/pull?since=…
  G-->>P: updates
  Note over P,G: re-pushing the same batch changes nothing
```

## 10 · Demo topology

```mermaid
flowchart LR
  A[A reporter] -- mock radio --> B[B relay no key]
  B -- mock radio --> C[C coordinator]
  C --> GW[Gateway optional]
  GW --> DASH[Dashboard optional]
  style B stroke-dasharray: 4 4
```
