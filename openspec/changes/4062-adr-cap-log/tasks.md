# Tasks

## 1. Restore the tracer and prove the filter

Reads: `tests/telemetry/test_telemetry.py`, `tests/roadmap/test_roadmap_alternatives.py`. Changes: the same files.

- [ ] 1.1 Call `reset_tracer()` at the end of `test_tracer_lifecycle_reset_and_shutdown`.
- [ ] 1.2 Emit a warning from `opentelemetry.sdk.trace.export` in the ADR cap test.
  - Verification: `$ uv run devops ci test tests/telemetry/test_telemetry.py tests/roadmap/test_roadmap_alternatives.py -n 0` passes
