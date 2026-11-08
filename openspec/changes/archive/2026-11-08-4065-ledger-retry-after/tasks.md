# Tasks

## 1. The ledger keeps a retry time and the class

Kind: behavior. Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/roadmap/failure.py`, `tests/roadmap/test_roadmap_ledger_retry_after.py`. Changes: `src/devops_cli/roadmap/run.py`, `tests/roadmap/test_roadmap_ledger_retry_after.py`, `tests/roadmap/test_roadmap_run_failure_ledger.py`, `tests/github/test_service_limits.py`, `tests/roadmap/stage/test_roadmap_stage_job.py`, `tests/roadmap/refine/test_roadmap_refine_placeholder.py`, `tests/server/test_service_state_unkept.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_ledger_retry_after.py`, write the tests of the criteria: `retry_after`, `half_open`, `new_input`, `old_record` and `class_cause`. Give the existing tests that call the ledger the time of the round and the class as the cause. Confirm that the new tests fail on `origin/main`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_ledger_retry_after.py`
- [x] 1.2 Give `FailureLedger.failed` and `FailureLedger.suspended` the parameter `now`. Keep `retry_after` in each entry, set it by the rule of the limit with `retry_after(cause)` from `roadmap/failure.py`, and compare it in `suspended`. Add the 6-field entry to `_FailedRounds` and write it in `_KeptRounds`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_ledger_retry_after.py tests/roadmap/test_roadmap_run_failure_ledger.py`
- [x] 1.3 In `_count_failure`, pass `failure_class_of(exc).value` for a `DevOpsCLIError` and `ci_infra` for another exception. In `_execute_due_rows`, pass `current_time` to `suspended` and `_count_failure`
  - Verification: `$ uv run devops ci test tests/roadmap tests/github/test_service_limits.py tests/server/test_service_state_unkept.py`

## 2. The gauges and the log line show the class and the time

Kind: behavior. Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`. Changes: `src/devops_cli/roadmap/run.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/config/constants.py`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 2.1 Add the constant `CONST_SERVICE_METRIC_JOB_RETRY_AFTER_SECONDS`, and write the tests of the label `class`, of the series of an old class, of the seconds gauge and of the log line. Confirm that they fail on `origin/main`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_ledger_retry_after.py tests/telemetry/test_telemetry_instruments.py`
- [x] 2.2 In `FailureLedger._report_locked`, set both gauges with the labels `repo`, `row` and `class`, and set the series of the old class to 0 when the class changes or the entry clears. Set the seconds gauge in `failed` and `suspended`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_ledger_retry_after.py tests/roadmap/test_roadmap_status_rows.py tests/github/test_service_limits.py`
- [x] 2.3 Change `MESSAGES.serve.job_suspended` so that it names the class and the time of the next probe round and keeps the list of new inputs. Pass the two values in `_count_failure`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_ledger_retry_after.py tests/github/test_service_limits.py`

## 3. The alert

Kind: manifests. Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/monitoring/prometheus-values.yaml`, `k8s/monitoring/dashboards/devops-cli.json`, `tests/grafana/test_grafana_dashboards.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/README.md`.

- [x] 3.1 Add the rule, the series and the promtool cases to `tests/prometheus/test_k8s_monitoring_alerting.py` and to the fixture `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`. Confirm that the run fails on `origin/main`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 3.2 Add `RoadmapServiceRowSuspended` to the group `roadmap-service` of `k8s/monitoring/prometheus-values.yaml`, with the expression, the wait and the annotations that the fixture states. Add the panel `Service Retry After Seconds` for the new gauge to the row Roadmap Service of the dashboard `devops-cli`, as `test_cli_dashboard_service_row_reads_each_series_of_the_service` asks for a query of each series
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 4. Fix the documents

Kind: documents. Reads: `k8s/README.md`, `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`. Changes: `k8s/README.md`, `docs/roadmap/stage.md`, `docs/ROADMAP_WORKFLOW.md`.

- [x] 4.1 In `k8s/README.md`, add a row for `RoadmapServiceRowSuspended` to the alert table and name it in the Roadmap service section. Change item 11 (the retry time, the class as the cause, and the removal of `service-failures.json` for a rollback to an older image), item 12 (the label `class` and the new gauge) and item 17 (the labels of the gauge). Fix the text of `docs/roadmap/stage.md` and `docs/ROADMAP_WORKFLOW.md` only where their wait text is wrong
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`
- [x] 4.2 Check the change and the specs
  - Verification: `$ uv run devops openspec check`

## Criteria

- Group 1: A suspended row runs after its time with no new input. A failed probe round sets a new time, and a success clears the entry. A new digest runs the row at once. An entry of 4 or 5 fields loads and keeps the digest rule. The ledger file holds the class value as the cause.
- Group 2: The gauge `devops_cli_service_job_suspended` has the label `class`, the series of an old class reads 0, the gauge `devops_cli_service_job_retry_after_seconds` holds the seconds left, and the log line names the class and the time.
- Group 3: The alert and its promtool case exist and `tests/prometheus/test_k8s_monitoring_alerting.py` passes.
- Group 4: The documents describe the retry time, the label and the alert.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
