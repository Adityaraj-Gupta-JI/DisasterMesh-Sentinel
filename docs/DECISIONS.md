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
