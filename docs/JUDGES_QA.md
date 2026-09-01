# Anticipated Questions

Short, honest answers. Where a claim has a test behind it, the test is named.

### Is this actually offline, or does it need a server?

Offline. The gateway is optional and the dashboard says so when it is unreachable. The
entire demo runs with no network stack involved: `test_10_the_whole_flow_ran_with_no_internet`.

### What stops the AI from making a bad call?

Three things. It never decides — it emits typed data into a deterministic engine. Rule
floors cannot be lowered by low confidence
(`test_ai_uncertainty_cannot_downgrade_a_rule_triggered_life_threat`). And no action —
dispatch, alert, closure — happens without an authorized human confirming it.

### Is the AI real?

Not yet. It is a deterministic rule engine over an English/Hindi/Tamil emergency
lexicon. Adapters for Whisper, XLM-R, mDeBERTa, multilingual-e5, and NLLB are defined
behind feature flags with no weights downloaded. The rule engine is not throwaway: it
is what runs on a phone that has no model, so it stays in production as the fallback.

### Does the volunteer relaying my report get to read it?

No. Payloads are AES-256-GCM encrypted; the relay holds no organisation key. It sees
routing metadata only — priority, size, expiry. `test_relay_carries_ciphertext_it_cannot_read`
asserts the relay cannot even reconstruct the incident, and
`test_relay_status_exposes_counts_but_no_content` asserts its own status screen leaks nothing.

### What happens when the photo is huge and someone is dying?

The text is a separate bundle from its attachments, and payload rank sits above
priority score in the scheduler's sort key. Within P0, text outranks its own photograph:
`test_p0_text_beats_p0_image`, plus a property test that holds under up to 20 competing
media objects.

### What if the connection drops halfway through a transfer?

The transfer resumes from the missing chunks on the next contact, and the file is only
committed after the whole-file digest matches. This was a real bug: delivery used to be
recorded on send, so an interrupted transfer was never re-offered. The simulator caught
it; ADR-0003 records the fix.

### Could someone flood it with fake emergencies?

Yes, and that is an accepted risk for the MVP — T1 in the threat model. TTL,
replication limits, and signed source ids bound the damage and make a flood
attributable, but there is no rate limiting or Sybil resistance. Both depend on
authenticated identity issuance, which is Phase 2.

### How do you know an audit log was not edited?

Each entry hashes its content plus the previous entry's hash. Editing, deleting, or
reordering breaks the chain, and there are tests for all three.

### Does it work in languages other than English?

English, Hindi, and Tamil, including code-switched reports like
"building collapse हुआ है, तीन लोग trapped हैं". A count expressed as "तीन", "மூன்று",
"three", or "3" all extract as 3 — and "some people" extracts as *unknown*, never as a
number.

### What is the weakest part?

The organisation payload key is pre-shared with no key exchange and no forward secrecy,
and identity issuance is unauthenticated. Everything else in the threat model that is
unmitigated traces back to that second point.

### Why is the Android app not running?

No Android SDK and no Gradle wrapper on this machine, and the installed JDK is newer
than AGP supports. The Kotlin exists — domain, priority engine, Room schema, Nearby
adapter, Compose UI — and its unit tests mirror the Python ones one for one, but none
of it has been compiled. It is the first item in KNOWN_LIMITATIONS for that reason.

### How much of this is tested?

395 automated tests: 324 core, 43 gateway, 20 AI service, 8 dashboard. Lint clean, type
check clean, dashboard builds. Zero known failures. Every MVP criterion has a named
test, listed in TRACEABILITY.md.

### Would you deploy this tomorrow?

No. It is a hackathon MVP verified in software, with no external security review, no
radio testing, and no load testing above three nodes. What it does demonstrate is an
architecture where the safety properties are structural rather than aspirational.
