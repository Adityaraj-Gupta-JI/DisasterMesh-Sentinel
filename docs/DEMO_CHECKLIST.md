# Demo Checklist

## T-30 minutes

- [ ] `make test` — expect 387 passed, 0 failed
- [ ] `make test-dashboard` — expect 8 passed
- [ ] `make simulate` — expect 10 scenarios, 9 delivering 1/1 or 2/2 and scenario 6 refusing 2
- [ ] `make demo` — read the output once, end to end
- [ ] `make reset-demo` — clean gateway state
- [ ] Terminal font large enough to read from the back of the room
- [ ] Laptop charged; the demo needs no network, so airplane mode is a fair flex

## T-5 minutes

- [ ] Close every unrelated window
- [ ] `cd /home/chetanjaat/disasap`
- [ ] Terminal 2 ready with `make run-backend`
- [ ] Terminal 3 ready with `make run-dashboard`
- [ ] KNOWN_LIMITATIONS.md open in an editor tab — you will be asked

## During

- [ ] Open with the problem, not the architecture
- [ ] Run `make demo`, narrate steps 1, 4, 5, 8
- [ ] Show the priority explanation lines — that is the differentiator
- [ ] Say "simulated" every single time dispatch comes up
- [ ] Say "never compiled" the first time Android comes up

## Hard rules

- [ ] Never claim the radios have been tested
- [ ] Never call it production-ready
- [ ] If something fails live, show the failure and move on
