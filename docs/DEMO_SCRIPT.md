# Demo Script

Six minutes, one terminal, no network. Every fallback is listed because the demo that
fails is the one with no fallback.

## Before you start

```bash
make reset-demo     # wipe gateway state, reseed simulated resources
make test           # 387 tests — run this once so you can say "all green"
```

Have two terminals open. Terminal 1 runs the demo. Terminal 2 is for questions.

---

## The 90-second version

```bash
make demo
```

Then talk over the output. It prints ten numbered steps; the four that matter:

**Step 1 — the decision, explained.** A collapse report scores P0 with its reasoning
printed line by line. Point at `RULE: trapped person with active hazard → P0 floor 85`.
That is a rule, not a model, and it cannot be argued down.

**Step 4 — the relay cannot read what it carries.** `B can decrypt: False`,
`B reconstructed: 0 incidents`. A stranger's phone moved the report without being able
to open it.

**Step 5 — text arrived before the photo.** `arrival order: INCIDENT_TEXT first`. The
120 KB image never delayed the sentence that says three people are trapped.

**Step 8 — the human gate.** `order created: RECOMMENDED (creating one dispatches
nothing)`, then `after human OK: ASSIGNED`. The AI proposed. A person authorized.

---

## The six-minute version

### 1 · The problem (30s)

Towers fall first and stay down longest. The people who need help most are the ones who
cannot reach it. Every phone in the crowd is a working radio for about a hundred metres.

### 2 · A report, offline (60s)

```bash
make demo-tamil
```

A Tamil report is classified, prioritised, encrypted, and queued — with no network and
no model weights. Note the detected language and that the original wording is
preserved untouched.

> If asked "is that a real model?" — no. It is a deterministic rule engine over a
> multilingual lexicon, and it is also exactly what runs on a phone with no model
> available. Real adapters exist behind feature flags. That is in KNOWN_LIMITATIONS §2.

### 3 · The mesh (90s)

The same run shows A → B → C with the relay unable to decrypt. Then:

```bash
make simulate
```

Ten adversarial scenarios: dropped links, a ten-minute wait for any coordinator, a 2 MB
routine file competing with a critical text, a 5% battery, an interrupted transfer, an
unauthorized node asking for medical content. Scenario 3 prints
`P0 text preceded bulk media: True`; scenario 7 prints
`P0 delivered at 5% battery: True` and `P3 deferred at 5% battery: True`.

### 4 · The coordinator (60s)

```bash
make run-backend      # terminal 2
make run-dashboard    # terminal 3, then open http://localhost:5173
```

Priority inbox, AI output in its own purple frame labelled "AI suggestion — a human
decides", uncertainty shown rather than hidden, dispatch behind a confirmation dialog
that says the word "simulated".

### 5 · The claim you can defend (60s)

```bash
cd protocol && python3 -m pytest -q
```

387 tests, including one that matters more than the rest:

```bash
python3 -m pytest tests/test_priority.py::test_ai_uncertainty_cannot_downgrade_a_rule_triggered_life_threat -v
```

A model that is 2% confident cannot downgrade "not breathing". That is the product.

---

## Fallbacks

| If this fails | Do this |
|---|---|
| The dashboard will not start | Skip it. `make demo` needs nothing but Python. |
| The gateway port is taken | `--port 8010`, or skip: the mesh does not need the gateway. |
| npm is missing | Skip the dashboard. It is the optional layer, by design. |
| Someone asks for the Android app | Say plainly: written, never compiled, no SDK here. Show the Kotlin priority engine next to the Python one and note the tests mirror each other. |
| Someone asks to see a real radio transfer | Say no. The mock models the interface, not the radio. Claiming otherwise would be the one thing this project refuses to do. |
| The simulator prints a failure | Show it. A failing scenario with an honest number beats a demo that hides one. |

## Never say

- "Production-ready." It is a hackathon MVP verified in software.
- "It works over Bluetooth." It has never touched a radio.
- "The AI decides." It never decides. That is the entire point.
- "It dispatches an ambulance." Every dispatch is simulated, and the data model cannot
  represent a non-simulated resource.
