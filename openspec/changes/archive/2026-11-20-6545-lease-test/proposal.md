# Proposal: #6545

## Why
`tests/k8s/test_lease.py::test_a_pod_that_another_pod_beat_to_the_create_tries_again` fails at random (#6545). In shard 4 of Service Image Tests on PR #6524 (job 136468721945), the test counted 3 Lease creates where it expects 2, and the log holds three 409 warnings of `pod-late`.

The test reads the count of creates when the fake clock reaches two retry periods. The pod sleeps alone, so `_LeaseClock.sleep` wakes it at once and does not give control back to the event loop. On CPython 3.14, `await asyncio.to_thread(...)` also returns with no yield when its thread ends before the loop adds its callback. Then the pod makes its next read and its third create before the test task runs.

Closes #6545.

## What Changes
- `_LeaseClock.sleep` gives control back to the event loop after each wake, as `asyncio.sleep` does. A task that waits for a mark then reads the state before the pod goes on.
- A new test shows that a task that waits for a mark reads before a sleeper that is alone goes on.
- The change alters no behavior that a consumer sees. It changes one test file, so it has no spec delta and sets `skip_specs: true`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. `LeaseHolder` in `src/devops_cli/k8s/lease.py` does not change.

## Impact
- The create-race test gives the same result on each run, so it does not fail a pull request that does not change the Lease code.
- No command, setting, manifest or product code changes. The change fits one pull request.

## Feasibility
- The log of job 136468721945 shows `assert (False, 3, True) == (False, 2, True)` at `tests/k8s/test_lease.py:186` on CPython 3.14.10.
- In CPython 3.14.10, `_chain_future` sets the asyncio future at once when its callback runs in the thread of the loop (`asyncio/futures.py:404`). CPython 3.12.14 always sets it through `call_soon_threadsafe` (`asyncio/futures.py:400`).
- A trace of the loop showed the cause: after the clock reached 4 s, the wakeup of the test task was in the ready queue. The thread then ran the read and the third create, and the loop ran no handle between them.
- With 16 xdist workers and 16 CPU-bound shell loops on 16 CPUs, the old test failed in 6, 5 and 3 of 3,000 runs. Each failure was `(False, 3, True)`. In one process with no load, it passed 500 of 500 runs.
- The new test failed with `[2.0, 4.0, 6.0]` before the fix. It also failed when `_wake` set the marks before it woke the sleepers, as the refined design of #6545 proposed.
- After the fix, on the same load, the create-race test passed 9,000 of 9,000 runs, and each test of the file passed 1,000 of 1,000 runs.

## Existing Tool Considered
looptime fakes the time of an asyncio event loop and could replace `_LeaseClock`. It adds a dependency and changes how each Lease test sets the time, where the fix is one line in the fake of the test. pytest and `asyncio.sleep(0)` cover the need. Cost: about 100k tokens and 1 hour, most of it for the reproduction and the trace.
