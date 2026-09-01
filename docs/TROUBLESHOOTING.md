# Troubleshooting

### `ModuleNotFoundError: No module named 'dms'`

The shared package lives in `protocol/`. Run tests from inside a project directory
(`cd protocol && python3 -m pytest`) or use the Makefile targets, which set
`PYTHONPATH` for you.

### `sqlite3.OperationalError: unable to open database file`

The parent directory does not exist. The mesh harness creates it; if you are
constructing a `SqliteStore` by hand, `mkdir -p` the directory first.

### The dashboard shows "Gateway unreachable"

Expected when the gateway is not running — and it is a feature: the banner exists
because the mesh works without the gateway. Start it with `make run-backend`, or ignore
it and use `make demo`, which needs nothing.

### 401 `invalid_credentials` from the gateway

The bearer token is not in `DMS_API_KEYS`, or `DMS_ENV=production` is set with no keys
configured, in which case nothing is authorized by design. In development, use
`dev-coordinator-key`.

### 400 `confirmation_required` on dispatch

Working as intended. Dispatch needs `?confirm=true` in addition to the
`ASSIGN_RESOURCE` permission. There is no way to configure this away.

### 404 on an incident that exists

You are authenticated as a different organisation. Cross-organisation reads return 404
rather than 403 so the API does not confirm another organisation's records exist.

### The relay receives bundles but shows zero incidents

Correct. A relay holds ciphertext without the organisation key, so it can carry and
forward but cannot reconstruct anything. `test_relay_carries_ciphertext_it_cannot_read`
asserts exactly this.

### `make apk` / `make test-android` exits 1

There is no Android SDK or Gradle wrapper on this machine. The targets fail loudly
rather than appearing to pass. See KNOWN_LIMITATIONS §1.

### The simulator reports a scenario as 0/1

Read the notes it prints — they say which step failed. This is the intended way to find
a regression; scenario 8 found a real delivery bug this way.

### Tests pass but the demo behaves differently

They should not. Both use the same harness, clock, and transport. If they diverge, the
demo is right and a test is missing — that gap is the bug.
