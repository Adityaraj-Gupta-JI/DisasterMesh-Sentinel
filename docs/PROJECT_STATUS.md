# Project Status

**Hackathon MVP — verified in software.** Not production-ready, and not radio-tested.

Full evidence in [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md); everything absent is
in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## One-line summary

All ten MVP acceptance criteria pass as named automated tests; 395 tests pass in total;
the Android client is written but has never been compiled.

## What a reviewer can run right now

```bash
make demo        # the whole product path, offline
make simulate    # ten adversarial network scenarios
make test        # 387 Python tests in ~4 seconds
```

## Component status

| Component | Status |
|---|---|
| Core mesh, protocol, crypto, sync, files, governance | VERIFIED |
| Priority engine and context policies | VERIFIED |
| AI rules and mock adapters (EN/HI/TA) | VERIFIED |
| Dispatch simulation | VERIFIED |
| Gateway API | VERIFIED |
| Simulator | VERIFIED |
| Dashboard | IMPLEMENTED — builds and type-checks, not browser-tested |
| Android client | WRITTEN — never compiled |
| Docker stack | WRITTEN — never run |
| Real ML models | NOT STARTED — deliberately |

## Next three things

1. Compile the Android module on a machine with the SDK and a JDK 17/21 — which also
   runs `PriorityContractTest` and completes the cross-language guarantee.
2. A two-device Nearby Connections test — the only way to validate the radio layer.
3. Authenticated identity issuance, which unblocks most of the unmitigated threats.

The cross-language drift risk (formerly the top item) is closed: a frozen contract is
read by both suites, and `make parity` catches divergence today without a Kotlin
compiler.
