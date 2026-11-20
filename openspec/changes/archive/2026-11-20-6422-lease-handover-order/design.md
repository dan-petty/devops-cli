# Design

## Decisions

- The handover test calls `lease_clock.leave()` after `await old.release()` returns. While the old pod gives the Lease back, the fake clock keeps two parties. The old pod does not sleep, so the clock does not move, and the waiting pod cannot see the Lease end. After the release, `leave()` wakes the waiting pod, and it takes the Lease at its next try.
- The docstring of `_LeaseClock.leave()` states when to call it: after the last API call of the holder that stops. From then on, each sleep of the other holder moves the clock at once, so a slow thread of the holder that stops lets the time pass.
- `LeaseHolder` in `src/devops_cli/k8s/lease.py` does not change. On a real clock, the release takes some milliseconds, and the waiting pod takes the Lease only after the 15 s duration with no renewal. When a release comes after that duration, a `False` result is correct.

## Rejected alternatives

- Stop the fake clock while a thread call of a holder runs: it adds state to the test clock for an order that the test can give itself. The clock already holds the time while both holders are parties.
- Change `release()` so that it calls the API without `asyncio.to_thread`: the call would block the event loop, and `LeaseHolder` documents that each API call runs in a thread so that the loop keeps serving. The probe shows no fault in the Lease code.
- A retry, a skip or a longer wait in the test: each one hides the race and keeps it.
