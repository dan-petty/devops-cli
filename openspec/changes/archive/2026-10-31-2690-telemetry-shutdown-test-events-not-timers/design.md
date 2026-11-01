# Design

## Problem Statement

The test `test_shutdown_joins_all_worker_threads` uses fixed wall-clock timers.
It waits for thread start with a 1.0 s deadline.
It releases the pending payload send using `threading.Timer(1.2, ...)`.
It sets a 3.0 s safety wait inside the mock payload send.
Under CPU load, threads take longer to start and timers fire late.
This behavior violates `docs/TESTING.md`, which prohibits tests with internal deadlines.

## Proposed Changes

1. Import `THREAD_HANDOFF_BOUND_SECONDS` from `tests.support.waits`.
2. Inside `slow_send`, wait for the `finish` event with `THREAD_HANDOFF_BOUND_SECONDS`.
3. In the main test thread, wait for the `started` event with `THREAD_HANDOFF_BOUND_SECONDS`.
4. Start `client.shutdown` in a dedicated thread named `test-otel-shutdown`.
5. Verify that `shutdown` is in progress and has not finished.
6. Set the `finish` event to release the in-flight send.
7. Join the shutdown thread with `THREAD_HANDOFF_BOUND_SECONDS`.
8. Assert that all telemetry worker threads are joined and the client executor is reset.

## Acceptance Criteria Verification

1. `tests/telemetry/test_telemetry_shutdown_sync.py` contains no `threading.Timer`.
2. The test contains no event waits with numeric deadlines.
3. The test suite passes repeatedly under load (`uv run devops ci test tests/telemetry/test_telemetry_shutdown_sync.py`).
