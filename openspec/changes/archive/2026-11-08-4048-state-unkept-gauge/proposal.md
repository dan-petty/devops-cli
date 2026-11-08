# Proposal

## Why

The roadmap Service keeps three records on its volume: the request budget, the halt and the failure ledger. When a write fails, `keep_state_record` writes one error log line and the Service goes on with memory only (#2474). Nothing else shows the fault. A restart then loses what the record held: the budget window, a halt after a refused identity, or the suspended jobs (#4048).

The log line stays. This change adds a gauge and an alert, so a person sees the fault without a log search.

## What Changes

- Add a `kind` argument to `keep_state_record` in `src/devops_cli/server/service.py`. The kind is a `StateRecord` string enum with the values `budget`, `halt` and `ledger`. Each of the four call sites passes its own kind: two in `RequestBudget`, one in `RoundPause`, one in `FailureLedger` of `src/devops_cli/roadmap/run.py`.
- Set the gauge `devops_cli_service_state_unkept` (constant `CONST_SERVICE_METRIC_STATE_UNKEPT`) with the label `record` in `keep_state_record`: 1 after a write error, 0 after the next write that works. `keep_state_record` still raises nothing.
- Add the alert `RoadmapServiceStateUnkept` (warning, for 15 minutes) to the group `roadmap-service` in `k8s/monitoring/prometheus-values.yaml`, with a promtool case in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`.
- Add a row for the alert to the alert table of `k8s/README.md`, and name the gauge in item 12 of the list of the Service.
- The change carries spec deltas, because the Service's `/metrics` and its alerts are behavior that a consumer observes: `skip_specs` is false.
- The gauge lives in the memory of the process. A restart clears it, and the next write error sets it again.
- The change adds one gauge and one alert. It removes, renames and tightens no setting, so `k8s/devops/configmap.example.yaml` and the live ConfigMap stay as they are. `tests/config/test_k8s_devops_runtime.py` already loads the example ConfigMap into `Settings`, so the change adds no new test for it. Nothing is applied to the cluster.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-service-limits`: The Service shows each state record that it could not write
- `roadmap-service-alerts`: A state record that stays unwritten warns

## Impact

- Code: `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/constants.py`
- Manifests: `k8s/monitoring/prometheus-values.yaml`
- Documents: `k8s/README.md`
- Tests: `tests/server/test_service_state_unkept.py` (new), `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/telemetry/test_telemetry_instruments.py`

## Feasibility

- I read these files at origin/main: `src/devops_cli/server/service.py` (`keep_state_record` at line 158, `RequestBudget.admit` at lines 232 and 260, the halt write at line 386), `src/devops_cli/roadmap/run.py` (`FailureLedger._keep_locked`, which is the only other call), `src/devops_cli/telemetry/metrics.py` (`set_gauge` at line 113 takes `labels`), `src/devops_cli/config/constants.py` (`CONST_SERVICE_METRIC_JOB_SUSPENDED`, the model for a gauge with labels) and the group `roadmap-service` of `k8s/monitoring/prometheus-values.yaml`.
- `git grep keep_state_record -- src tests` at origin/main finds exactly four call sites and three kinds. The claim of three kinds is a claim about a set, and the count comes from that command.
- A real write error needs no patch: a record whose parent is a regular file raises `NotADirectoryError` or `FileExistsError`, which are `OSError`. `uv run devops ci test tests/server/test_service_state_unkept.py` shows that the 9 tests that need the gauge fail on the base because the series do not exist, and the test that reads a bad record passes.
- `promtool` (in `~/.local/bin`) runs the rule tests; `tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base for the new alert in `test_the_baseline_rule_set`, in the rule list, and in the promtool run of the group `roadmap-service`.
- No merged pull request, open pull request or newer issue does this work: searches for `state_unkept` and `keep_state_record` find only #4048. #4042 is merged, so `run.py` is current.
- I did not run the Service. The gauge is read from `GLOBAL_METRICS`, which the Service serves on `/metrics` as it serves `devops_cli_service_job_suspended`.

## Existing Tool Considered

The gauge helpers of `GLOBAL_METRICS` (prometheus_client) and the existing alert group `roadmap-service` cover the need. No library is needed, and the change deletes no internal code. The cost is the one in the issue: about 40k tokens and 2 hours to build, 2k tokens a quarter to keep, and 10k tokens and 0.5 hours to fix.

## Dependencies

None. #4042 is merged.
