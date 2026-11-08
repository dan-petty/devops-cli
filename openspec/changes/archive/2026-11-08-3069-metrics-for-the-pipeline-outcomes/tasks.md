# Tasks

## 1. Metrics constants and store record keys (behavior)

- [x] 1.1 Add failing tests for `ImplementRecordKey.REPAIR_ROUNDS` and metric constants
  Verification:
    `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_records.py`
- [x] 1.2 Add `CONST_SERVICE_METRIC_IMPLEMENT_JOBS`, `CONST_SERVICE_METRIC_IMPLEMENT_REPAIR_ROUNDS`, `CONST_SERVICE_METRIC_IMPLEMENT_TOKENS`, `CONST_SERVICE_METRIC_IMPLEMENT_CONSECUTIVE_FAILURES`, and `CONST_SERVICE_CONSECUTIVE_FAILURES_FILENAME` to `src/devops_cli/config/constants.py`, and add `REPAIR_ROUNDS` to `ImplementRecordKey` in `src/devops_cli/roadmap/stores/store.py`
  Verification:
    `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_records.py`

## 2. Consecutive failures tracking and persistence (behavior)

- [x] 2.1 Add failing tests for consecutive failures tracking, restart persistence, class resets, and delivered resets
  Verification:
    `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_consecutive_failures.py`
- [x] 2.2 Implement `ConsecutiveFailures` state management and persistence in `src/devops_cli/roadmap/implement/consecutive_failures.py`
  Verification:
    `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_consecutive_failures.py`

## 3. Counter zero-priming at Service start (behavior)

- [x] 3.1 Add failing tests for zero-primed implement counter label sets at Service startup
  Verification:
    `$ uv run devops ci test tests/telemetry/test_service_counter_series.py`
- [x] 3.2 Update `prime_service_counters` in `src/devops_cli/server/counter_series.py` and register the series in `tests/telemetry/test_telemetry_instruments.py`
  Verification:
    `$ uv run devops ci test tests/telemetry/test_service_counter_series.py`

## 4. Implement runner and submit pipeline metrics (behavior)

- [x] 4.1 Add failing tests for repair rounds in item job record, implement jobs counter, repair rounds counter, and tokens counter
  Verification:
    `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py`
- [x] 4.2 Record repair rounds in `implement_run.py`, and emit implement jobs, repair rounds, tokens, and consecutive failure metrics from `_report` in `src/devops_cli/roadmap/implement/implement_submit.py`
  Verification:
    `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_submit.py`

## 5. Stage counter repository label (behavior)

- [x] 5.1 Add failing test asserting that `devops_cli_roadmap_stage_total` carries the `repo` attribute
  Verification:
    `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job.py`
- [x] 5.2 Pass `repo` to `emit_stage_results` in `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/run.py`, and `src/devops_cli/commands/roadmap.py`
  Verification:
    `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_job.py`

## 6. Telemetry and cluster documentation (documents)

- [x] 6.1 Update `k8s/README.md` and `src/devops_cli/docs/generator.py` with descriptions of the new metrics and labels, and regenerate documentation
  Verification:
    `$ uv run devops docs generate --sync-readme && uv run devops ci docs`
- [x] 6.2 Verify full test and quality gates
  Verification:
    `$ uv run devops ci test tests/telemetry/ tests/prometheus/ tests/roadmap/`

## Workflow follow-up

- The dashboard, its GitOps provision and its panel checks: #3655.
- The alerts and their runbook entries: #3655.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
