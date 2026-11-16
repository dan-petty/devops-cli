# Tasks

## 1. Periodic metric export

- [x] 1.1 Write failing tests: a long command exports before it ends, a periodic export and a round flush count each delta once in time order, a short command exports once, and the interval comes from `OTEL_METRIC_EXPORT_INTERVAL`
  - Verification: `$ uv run devops ci test tests/telemetry/test_periodic_metric_export.py`
- [x] 1.2 Export the metrics at the interval from a thread that calls `flush()`, and stop the thread in `shutdown()`
  - Verification: `$ uv run devops ci test tests/telemetry/test_periodic_metric_export.py`

## 2. Export at SIGTERM

- [x] 2.1 Write failing tests: SIGTERM exports and then runs the handler before, two installs keep one handler, the entry point sets it, and a child with the default action exports and SIGTERM ends it
  - Verification: `$ uv run devops ci test tests/telemetry/test_sigterm_export.py`
- [x] 2.2 Add `devops_cli.telemetry.sigterm_export`, call it in `devops_cli.entry.main`, and reset it in the test floor
  - Verification: `$ uv run devops ci test tests/telemetry/test_sigterm_export.py`

## 3. Documents

- [x] 3.1 List `OTEL_METRIC_EXPORT_INTERVAL` in `docs/ENV_VARS.md` and tell in `docs/TELEMETRY.md` when a process exports its metrics
  - Verification: `$ uv run devops ci docs`

- Pending a person: after the deploy, `count_over_time(devops_cli_ai_tokens_total{job="roadmap-implement"}[10m])` shows about one sample a minute while a runner Job runs.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
