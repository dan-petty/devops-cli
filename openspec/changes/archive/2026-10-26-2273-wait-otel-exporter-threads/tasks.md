# Tasks

## 1. Failing test

- [x] Add failing test in `tests/test_telemetry_shutdown_sync.py` proving shutdown leaves no live worker threads
  - Verification: `uv run devops ci test tests/test_telemetry_shutdown_sync.py`

## 2. Telemetry client and logging bridge fix

- [x] Update `OTelTelemetryClient.shutdown()` in `src/devops_cli/telemetry/tracer.py` to join executor worker threads with `wait=True`
  - Verification: `uv run devops ci test tests/test_telemetry.py`
- [x] Update `_resolve_exporter()` in `src/devops_cli/telemetry/logging_bridge.py` to avoid instantiating a tracer if none is active
  - Verification: `uv run devops ci test tests/test_telemetry_logging_bridge.py`
- [x] Update `reset_tracer()` in `src/devops_cli/telemetry/tracer.py` to detach the logging handler before dropping and shutting down the tracer
  - Verification: `uv run devops ci test tests/test_telemetry.py`

## 3. Verification and static checks

- [x] Verify fail-to-pass check run passes against base
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify full static checks pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
