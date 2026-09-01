# Known Limitations

Everything this prototype cannot do, stated plainly. If a claim is not in
[DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md) with a passing test behind it, assume
it is on this page instead.

## 1. The Android app is blocked by local SDK setup

16 Kotlin files (2,224 lines) exist: domain model, priority engine, Room schema,
Nearby Connections adapter, design system, and the reporter/relay/coordinator screens.
The Gradle wrapper runs, but the debug APK cannot finish compiling on this machine yet.

- `ANDROID_HOME` is unset and no Android SDK was found in the usual user, Program Files,
  or project locations.
- The default `java` on PATH is Java 8, which is too old for the Android Gradle Plugin.
  IntelliJ's bundled JDK is new enough to pass that stage.
- **No radio test has been run between two physical devices.** Nearby Connections
  discovery, connection, and payload behaviour are unverified in reality.

What this means for a demo: the mesh demonstration runs on the mock transport, which
is a faithful model of the *interface* but not of radio behaviour — not of range,
interference, Android power management, or permission prompts. Do not describe the
mock as evidence that the radios work.

The Kotlin logic mirrors the Python reference implementation deliberately, and its
unit tests are written to the same expectations, so the first compile should surface
type errors rather than design errors. That is a hope, not a measurement.

## 2. The AI is a rule engine, not a trained model

Every "AI" path currently runs a deterministic rule engine over a hand-written
multilingual lexicon. Real adapters (Whisper, XLM-R, mDeBERTa, multilingual-e5, NLLB)
are defined behind feature flags but **no weights were ever downloaded or run**.

Consequences:

- Triage generalises only as far as the lexicon. A report phrased outside it lands as
  `UNKNOWN` with low confidence — safely, but unhelpfully.
- Transcription is a fixture lookup keyed on the first two bytes of the audio. It does
  not transcribe anything.
- Translation is a small glossary substitution, not translation.
- Embeddings are hashed bag-of-words, so cross-language similarity works only through
  shared lexicon terms.

The rule engine is not merely a stand-in: it is what runs on a phone with no model and
no network, so it must stay correct. But it is not a language model.

## 3. Sync is single-purpose and unoptimised

- Inventory exchange sends an **exact list** of bundle ids. That is fine for a
  hackathon-scale mesh and will not scale to thousands of bundles; the `InventoryDigest`
  interface exists so a Bloom filter can replace it, but none is implemented.
- The exchange needs several rounds to move a bundle two hops, because a relay only
  re-offers what it has already received.
- There is no congestion control, no fragmentation beyond fixed chunking, and no
  bandwidth estimation.

## 4. Cryptography is prototype-grade

- The organisation payload key is a **pre-shared symmetric key** distributed out of
  band. There is no key exchange, no per-incident keys, and no forward secrecy.
- Key rotation and revocation are modelled (`revoke()`, revocation checks in signature
  verification) but there is no distribution mechanism for a revocation list.
- Keys live in a software keystore. The Android Keystore path is written but, like the
  rest of the Android module, uncompiled.
- The design has not been reviewed by a cryptographer.

## 5. The gateway is a prototype

- Authentication is a static bearer-token map. There are no sessions, no rotation, no
  rate limiting, and no lockout.
- SQLite by default. PostgreSQL is supported by the SQLAlchemy layer but untested.
- No WebSocket/SSE push: the dashboard polls every 5 seconds.
- Attachment **metadata** is registered through the API; the bytes themselves move over
  the mesh, not through the gateway.

## 6. The dashboard has not been exercised in a browser

It type-checks, its logic is unit-tested, and it builds — but no one has clicked
through it against a live gateway. Layout under real data, focus order, and screen
reader behaviour are unverified.

## 7. Geography is approximate

Distance uses a haversine formula on WGS84 points with no map, no road network, and no
routing. "2 km apart" means straight-line distance, which in a flood may be irrelevant.

## 8. Nothing here is a real dispatch

Every resource is `simulated=True`, enforced at the type level: the gateway schema
literally cannot represent a non-simulated resource. No integration with any real
emergency service exists, and adding one is an explicit human-approval gate.

## 9. Not verified at all

- Docker Compose and both Dockerfiles (docker is not installed here).
- Battery consumption. The simulator's energy figure is a crude bytes-and-contacts
  model, not a measurement.
- Behaviour above a handful of nodes: the largest tested mesh is three.
- Any deployment concern — TLS termination, backups, monitoring, log retention.

## 10. Scope deliberately left out

Voice recording UI, image capture UI, map view, push notifications, multi-organisation
federation, responder mobile app, and public alerting beyond the authorization gate.
