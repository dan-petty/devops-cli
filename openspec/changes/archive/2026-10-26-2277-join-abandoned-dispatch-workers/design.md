# Design

## Cause

A dispatch that passes its timeout returns exit code 124 and leaves its worker thread running.
The worker still holds the command. When the command returns, `_execute_traced_cli_command` calls `record_metric`, and `record_metric` calls `get_tracer()`.
`get_tracer()` builds the global tracer on its first call, from the settings the process has at that moment.
After the floor tears down the test, the settings are the real ones: telemetry is on and the endpoint is port 4318.
The `devops-otel` thread of that new tracer connects to loopback port 4318, and the floor guard fails the test that is running.
`reset_tracer()` cannot help: it ran before the tracer existed.

## Fix

1. `InProcessDispatcher._dispatch_typer` starts the worker with `name=CONST_MCP_DISPATCH_THREAD_NAME`.
   The name makes the worker findable by thread name, and it is clearer than `Thread-3 (_worker)` in a thread dump.
2. `tests/conftest.py` gets an autouse fixture `finish_abandoned_dispatch_workers` that depends on `isolate_devops_cli_config`.
   A fixture that depends on another fixture is set up after it and torn down before it.
   The wait therefore happens while the test config, the environment and the tracer reset of that fixture still hold.
   The worker finishes against the isolated tracer: telemetry is off, and the refusing port is the endpoint.
3. The fixture joins every live thread with that name, with a bound of `_DISPATCH_WORKER_JOIN_SECONDS`.
   A worker that is alive after the bound fails the test at its own teardown and names the thread, so a leak shows in the test that causes it.

## Test

The floor invariant test runs two inner tests under the floor with `pytester`.
The first inner test hangs a command, lets the dispatch time out, releases the command, and slows the end of the worker with a patched `_record_cli_success`.
The second inner test checks that the worker has finished.
Without the fixture the second inner test fails, because it starts while the worker sleeps.
