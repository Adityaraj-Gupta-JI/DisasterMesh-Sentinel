# Abuse Cases

Not attacks on the system — misuse *of* it, by people who are authorized. These matter
more in practice than exotic exploits, and most are mitigated by process rather than code.

## A1 · A volunteer reads someone's medical emergency

**Mitigated in code.** A relay has no organisation key and fails `can_read_plaintext`.
It sees priority, size, and expiry. Its own status screen is asserted content-free.

## A2 · A coordinator quietly downgrades an inconvenient incident

**Partly mitigated.** Overrides are permitted — a human closer to the ground should be
able to correct a machine — but every override is recorded with actor, role, reason, and
timestamp in a hash-chained ledger. The system makes it visible, not impossible.

## A3 · Location used to find someone who does not want to be found

**Partly mitigated.** The reporter chooses precision per report; without
`VIEW_PRECISE_LOCATION` everyone sees ~1 km coarsening, and the UI shows when a location
has been blurred. Not mitigated: an authorized responder can still see exact positions.
This is a real residual risk for vulnerable reporters and is deliberately called out
rather than buried.

## A4 · Dispatch is claimed as real to impress an audience

**Mitigated by design.** `simulated=True` is enforced at the type level — the gateway
schema cannot represent a non-simulated resource — and the word appears in the data
model, the API response, the confirmation dialog, the audit entry, and the demo script's
"never say" list.

## A5 · The audit log is used to punish reporters

**Not mitigated.** The ledger records who reported what. `EXPORT_AUDIT` is restricted to
authority and administrator roles, but a hostile authority is outside this system's
threat model. Any real deployment needs a retention policy and an oversight mechanism
before this becomes a live risk.

## A6 · An organisation reads another organisation's incidents

**Mitigated in code.** Every query is organisation-scoped; cross-org reads return 404;
an id collision across organisations returns 409 rather than overwriting. Tested.

## A7 · The system is used for routine logistics and drowns real emergencies

**Mitigated.** Priority classes and TTLs exist for exactly this. Routine logistics is
P3 with 48-hour TTL, low replication, no acknowledgement requirement, and it is shed
first when battery drops. A large P3 file cannot delay a P0 text — property-tested.

## A8 · Someone builds a public "who is trapped" map from relayed metadata

**Partly mitigated.** Offers deliberately carry no content, but they do carry priority,
category, and timing. An observer who is offered bundles can infer that severe
incidents are occurring nearby, though not who or what. Full metadata privacy would
need cover traffic, which is out of scope.
