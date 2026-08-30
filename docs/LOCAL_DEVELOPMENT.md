# Local Development

Environment verified 2026-08-31 on Fedora (Linux 7.1.9), Bash.

## Present

`git 2.55.0` · `python3 3.13.9` · `pip 25.3` · `node 22.22.2` · `npm 10.9.7` ·
`java 25.0.4` · `make 4.4.1` · `ruff 0.12.0` · `pytest 8.4.2`

## Missing / blocked

| Gap | Effect | Fix |
|---|---|---|
| `gradle` not installed, no wrapper committed | No Android build | Commit a Gradle wrapper with the Android module, or install Gradle |
| `ANDROID_HOME` unset | SDK not discoverable | `export ANDROID_HOME=$HOME/Android/Sdk` |
| `cmdline-tools` absent from SDK | Cannot accept licenses or fetch packages via CLI | Install via Android Studio SDK Manager |
| JDK 25 only | Likely newer than current AGP supports | Install and pin JDK 17 or 21 for the Android module |
| `docker` not installed | Compose workflows unverifiable | Install Docker, or run backend and AI service directly |

Android APK builds are **not** verified in this environment. Do not claim otherwise.

## Start

```bash
cp .env.example .env     # fill in placeholders; .env is git-ignored
make help                # list targets
make status              # show which subprojects exist
```

Targets for subprojects that do not exist yet fail with a `BLOCKED:` message. That
is intentional — see `docs/DEVELOPMENT_STATUS.md` for what has actually been built.

## Once scaffolded

```bash
make test            # all Python tests
make run-backend     # http://127.0.0.1:8000
make run-ai          # http://127.0.0.1:8001 (mock mode)
make run-dashboard   # http://localhost:5173
make lint && make fmt
```

## Mock mode

The whole critical path (incident → priority → bundle → relay → coordinator →
acknowledgement → simulated dispatch) is designed to run with `DMS_AI_MODE=mock` and
the in-memory mock transport — no phones, no models, no Internet. This is the
default development mode and the fallback demo path.
