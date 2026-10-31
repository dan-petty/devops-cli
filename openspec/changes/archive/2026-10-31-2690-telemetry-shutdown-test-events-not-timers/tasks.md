# Tasks

- [x] Update `tests/telemetry/test_telemetry_shutdown_sync.py` to remove `threading.Timer` and use event coordination with `THREAD_HANDOFF_BOUND_SECONDS`. <!-- id: 1 -->
- [x] Verify test execution with `uv run devops ci test tests/telemetry/test_telemetry_shutdown_sync.py`. <!-- id: 2 -->
- [x] Run static checks and OpenSpec validation. <!-- id: 3 -->
