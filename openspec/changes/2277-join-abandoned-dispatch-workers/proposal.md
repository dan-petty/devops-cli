# Proposal

## Why

Issue #2277: a test fails at teardown with "network edge reached without a fake", because a `devops-otel` thread connects to the loopback OpenTelemetry port 4318.
The test that fails is not the test that started the thread.
Pull request #2274 made `OTelTelemetryClient.shutdown()` wait for its threads, and the failure stayed.
The cause is not a client that a reset misses. The client does not exist yet when the reset runs.

`InProcessDispatcher._dispatch_typer` runs a command in a worker thread.
When the command passes its timeout, the dispatcher returns exit code 124 and leaves the worker running: Python cannot stop a thread.
Two tests hang a command on purpose and release it in a `finally` block, so the abandoned worker finishes while the test tears down.
At its end the worker calls `record_metric`, and `record_metric` calls `get_tracer()`.
If the floor has already reset the tracer and restored the environment, `get_tracer()` builds a new tracer from the real settings.
The default `telemetry.enabled` is `true` and the default endpoint is port 4318, so the new tracer exports to loopback port 4318 from a `devops-otel` thread.
The floor guard records the connect in whichever test runs next. The race depends on the load of the host, which is why the failure is intermittent.

## What Changes

- Name the dispatcher worker thread with `CONST_MCP_DISPATCH_THREAD_NAME`.
- Add an autouse fixture to `tests/conftest.py` that waits for dispatcher workers at the end of each test, while the isolated configuration and the tracer reset still hold.
  The fixture fails the test if a worker is still alive after the wait.
- Add a floor invariant test that fails when the next test starts before the abandoned worker has finished.
- The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/mcp/dispatcher.py`, `src/devops_cli/config/constants.py`.
- Tests: `tests/conftest.py`, `tests/invariants/test_hermetic_floor.py`.

## Feasibility

- Premise confirmed against the code and a run of the code.
  A scratch test dispatched a hung command with a 0.1 second timeout and released it after the fixtures had torn down, with no user configuration loaded.
  The abandoned `Thread-1 (_worker)` created a new tracer with `enabled=True` and the default endpoint, and `devops-otel_0` exported while the next test was in setup.
  The next test then failed at teardown with "network edge reached without a fake".
- In the same scratch run with the worker released inside the test, the worker used the isolated tracer and nothing was exported.
- The two tests that hang a command, `test_mcp_tool_stops_at_timeout_when_command_never_returns` and `test_in_process_dispatcher_timeout_stops_command_within_budget`, are the only places that abandon a worker.
- The port is not added to a list of allowed connections. The floor is right to refuse it.

## Existing Tool Considered

`threading.Thread.join` waits for the worker. Python has no way to stop a thread, so the product keeps the abandoned worker and the floor waits for it.
`pytest` fixture teardown order puts a fixture that depends on `isolate_devops_cli_config` before the reset of that fixture and before the restore of the environment.
No new library is necessary.
