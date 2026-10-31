# Proposal

## Why

Issue #2690 records that `tests/telemetry/test_telemetry_shutdown_sync.py` fails on a loaded host.
The test uses fixed timers and short deadlines to coordinate worker threads.
On a loaded system, thread scheduling delays cause these timers to expire prematurely.
The document `docs/TESTING.md` requires tests to wait on events with `THREAD_HANDOFF_BOUND_SECONDS`.
Tests must not use custom deadlines or timer threads.

## What Changes

Update `test_shutdown_joins_all_worker_threads` in `tests/telemetry/test_telemetry_shutdown_sync.py`:
- Replace the 1.0 s wait on the `started` event with `THREAD_HANDOFF_BOUND_SECONDS`.
- Replace the 3.0 s wait on the `finish` event in `slow_send` with `THREAD_HANDOFF_BOUND_SECONDS`.
- Remove the `threading.Timer` call.
- Run client shutdown in a worker thread.
- Signal the `finish` event from the test thread to unblock the send operation.
- Join the shutdown thread with `THREAD_HANDOFF_BOUND_SECONDS`.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `tests/telemetry/test_telemetry_shutdown_sync.py`: The test becomes deterministic and finishes faster.

## Feasibility

- The test coordinates threads using standard library `threading.Event` and `threading.Thread`.
- `THREAD_HANDOFF_BOUND_SECONDS` is already available in `tests.support.waits`.
- The product implementation in `devops_cli.telemetry.tracer` remains unchanged.

## Existing Tool Considered

`tests/support/waits.py` provides `THREAD_HANDOFF_BOUND_SECONDS`.
No external library is needed.
