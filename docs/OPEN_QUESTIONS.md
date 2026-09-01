# Open Questions

Decisions that need a human, listed with the options and a recommendation.

## 1 · How are node identities issued?

Today anyone can generate a keypair. Sybil resistance, rate limiting, and revocation
distribution all depend on the answer, and they are the largest unmitigated cluster in
the threat model.

Options: organisation-issued credentials with enrolment (strong, needs infrastructure);
web-of-trust between responders (no infrastructure, weaker); accept anonymity and rely
on coordinator triage (simplest, keeps the flooding risk).
**Recommendation:** organisation enrolment for responders, anonymous reporting for
citizens. A citizen in danger should never be blocked by a credential check.

## 2 · How is the organisation payload key distributed?

Currently pre-shared out of band with no rotation and no forward secrecy.
**Recommendation:** per-incident content keys wrapped to recipient public keys. It is
the right design and it is real work; the pre-shared key is honest for a prototype.

## 3 · Should a relay be able to see incident category?

It currently sees priority, size, and expiry — enough to schedule, and enough to infer
that something severe is happening nearby (abuse case A8).
**Recommendation:** keep it. Priority-aware relaying is the product; cover traffic is
the only real fix and it costs battery that a disaster cannot spare.

## 4 · How long should an incident be retained after resolution?

No retention policy exists. The audit ledger keeps everything forever, which is good
for accountability and bad for privacy (abuse case A5).
**Recommendation:** an explicit organisation policy, defaulting to 30 days for incident
content and longer for audit metadata without content.

## 5 · Who may override a rule-triggered P0 floor?

Currently any role with the ability to override, with a logged reason.
**Recommendation:** restrict downward overrides of a life-threat floor to a coordinator
or above, and surface them prominently in the inbox rather than only in the audit log.

## 6 · Should the dashboard show a map?

Deliberately omitted: a map above incident details is decoration during a crisis.
**Recommendation:** add a map *inside* the incident detail, never above the queue.

## 7 · What happens when storage is full and everything is live?

There is a cap but no eviction policy (threat T14).
**Recommendation:** evict lowest priority, then furthest from expiry, and tell the user.
Never evict an unacknowledged P0 — surface it as an alarm instead.
