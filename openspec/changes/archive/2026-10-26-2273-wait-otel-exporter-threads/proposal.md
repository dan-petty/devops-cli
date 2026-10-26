# Proposal

## Why

Issue #2273: `OTelTelemetryClient.shutdown()` calls `self._executor.shutdown(wait=False, cancel_futures=True)`.
The background worker threads continue to run after client shutdown and after tracer reset.
In test runs, the remaining threads make HTTP requests to the loopback OpenTelemetry port 4318 during subsequent tests.
The test harness loopback guard detects these unexpected connections and fails innocent tests.
The client shutdown must wait for all worker threads to terminate cleanly.

## What Changes

- Shut down the executor with `wait=True, cancel_futures=True` outside the client lock to prevent deadlocks and thread leaks.
- In `_resolve_exporter`, check if the global tracer exists and is enabled instead of instantiating a new tracer.
- In `reset_tracer`, detach the logging handler before dropping and shutting down the global tracer.
- Add an offline test verifying that client shutdown joins all worker threads before returning.
- The change sets `skip_specs: true` in `.openspec.yaml`.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/telemetry/tracer.py`, `src/devops_cli/telemetry/logging_bridge.py`.
- Tests: `tests/test_telemetry_shutdown_sync.py`.

## Feasibility

- Premise confirmed against `OTelTelemetryClient` implementation and CI failure logs in GitHub Actions run 40250039101.
- In unpatched code, `client.shutdown()` returned immediately while `devops-otel` threads remained alive.
- Calling `self._executor.shutdown(wait=True, cancel_futures=True)` outside `self._client_lock` joins all worker threads without deadlocks.
- Detaching `OTelLoggingHandler` before `dropped.shutdown()` ensures log calls during shutdown do not re-create the global tracer.

## Existing Tool Considered

`concurrent.futures.ThreadPoolExecutor` provides the `shutdown(wait=True, cancel_futures=True)` seam.
`OTelTelemetryClient` already uses this executor.
No new external library is necessary.
