# Proposal

## Why

The issue #3069 reports that the roadmap Service records pipeline outcomes in job records and labels without bounded metrics.
No metric shows implement outcomes by item class, repair rounds, tokens per delivered item, or consecutive failures of the same class in a row.
The metric `devops_cli_roadmap_stage_total` counts plans, but it has no `repo` label to separate counts by repository.
This change delivers these metrics and records the repair-round count in the job record.
The dashboard and alerts remain in #3655.

## What Changes

- Add `devops_cli_service_implement_jobs_total` with labels `repo`, `item_class`, and `result` to count reported runner Jobs.
- Add `devops_cli_service_implement_repair_rounds_total` with labels `repo` and `item_class` to count repair rounds.
- Add `devops_cli_service_implement_tokens_total` with labels `repo` and `item_class` to count tokens from reported runner Jobs.
- Add `devops_cli_service_implement_consecutive_failures` gauge with labels `repo` and `class` to record stops in a row of the same failure class.
- Persist the consecutive-failure gauge value across Service restarts in a state record file.
- Add the `repo` label to `devops_cli_roadmap_stage_total`.
- Record the integer repair-round count of each implement step in `item.job_record` under `ImplementRecordKey.REPAIR_ROUNDS`.
- Initialize zero series at Service startup for all new implement counters across known label sets.
- Update `k8s/README.md` and `docs/TELEMETRY.md` to document the new metrics and labels.

The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-job`: The Service records repair rounds in the item record and emits pipeline outcome metrics from reported runner Jobs.
- `roadmap-service-counters`: The Service primes zero series for the new implement counters at startup.
- `roadmap-stage`: The stage counter carries the repository name in the `repo` attribute.

## Impact

- Code: `src/devops_cli/roadmap/implement/implement_submit.py`, `src/devops_cli/roadmap/implement/implement_run.py`, `src/devops_cli/roadmap/stores/store.py`, `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/server/counter_series.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/docs/generator.py`.
- Documents: `k8s/README.md`, `docs/TELEMETRY.md`.
- Tests: `tests/roadmap/implement/test_roadmap_implement_submit.py`, `tests/telemetry/test_service_counter_series.py`, `tests/telemetry/test_telemetry_instruments.py`, `tests/prometheus/test_implement_failure_labels.py`, `tests/roadmap/stage/test_roadmap_stage_job.py`.

## Feasibility

- The Service reports runner Jobs in `_report` in `src/devops_cli/roadmap/implement/implement_submit.py`. It inspects the `state` of the ended Job and whether it settled as a stop.
- The token spend is recorded in `implement.spend` as JSON by `apply_implement` in `src/devops_cli/roadmap/implement/implement_run.py`.
- The repair rounds are available in `StepOutcome.repair_rounds` during step execution in `implement_run.py`.
- The failure taxonomy `FailureClass` in `src/devops_cli/roadmap/failure.py` defines bounded failure classes.
- The `FailureLedger` pattern in `src/devops_cli/roadmap/run.py` demonstrates persistent state management with atomic JSON file writes.
- The counter priming function `prime_service_counters` in `src/devops_cli/server/counter_series.py` initializes counter series at zero.
- The stage results emitter `emit_stage_results` in `src/devops_cli/roadmap/stage/stage.py` sends OTLP metrics for `ROADMAP_STAGE_TOTAL`.

## Existing Tool Considered

Grafana and Prometheus cover dashboard rendering, rule evaluation, and alert notification.
However, Prometheus requires the Service process to emit these domain-specific pipeline metrics and persist consecutive failure counters.
Building the Service instrumentation and state record costs approximately 20,000 tokens to build, keep, and fix, and 2 days of elapsed time.
No external library is replaced, and no unused internal code is retained.
