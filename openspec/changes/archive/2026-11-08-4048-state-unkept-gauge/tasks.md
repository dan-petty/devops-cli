# Tasks

## 1. Show a state record that the Service could not write

Kind: behavior. Reads: `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/telemetry/metrics.py`. Changes: `src/devops_cli/server/service.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/config/constants.py`, `tests/server/test_service_state_unkept.py` (new).

- [x] 1.1 Add `tests/server/test_service_state_unkept.py`: a record whose parent is a regular file makes the write fail. Assert for the budget, the halt and the ledger that the gauge series of the record reads 1, that `admit` raises nothing and one error line is logged, that the next good write sets the series to 0, that the other records have no series, and that a record that cannot be read still stops the start. The tests pin the exported name `devops_cli_service_state_unkept` as a literal, as the alert reads it, so they import no new name and fail in the call phase on the base. Run the file and see it fail
  - Verification: `$ uv run devops ci test tests/server/test_service_state_unkept.py` fails on the base because the series do not exist
- [x] 1.2 Add the constant `CONST_SERVICE_METRIC_STATE_UNKEPT` (`devops_cli_service_state_unkept`) to `src/devops_cli/config/constants.py`, beside `CONST_SERVICE_METRIC_JOB_SUSPENDED`. Add the `StateRecord` string enum (`budget`, `halt`, `ledger`) and the `kind` argument to `keep_state_record`. Set `CONST_SERVICE_METRIC_STATE_UNKEPT` with the label `record` to 1 in the `except OSError` branch and to 0 after a good write. Pass the kind at the four call sites: two in `RequestBudget`, one in `RoundPause`, and `FailureLedger._keep_locked` in `src/devops_cli/roadmap/run.py`. Write the gauge name in the docstring of `keep_state_record`
  - Verification: `$ uv run devops ci test tests/server/test_service_state_unkept.py tests/github/test_service_limits.py tests/roadmap/test_roadmap_run_failure_ledger.py` passes

## 2. Add the alert RoadmapServiceStateUnkept

Kind: manifest. Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/telemetry/test_telemetry_instruments.py`.

- [x] 2.1 Add the promtool cases to `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, add the alert to the rule list and the baseline list, and the gauge name to `SERVED_SERIES`, of `tests/prometheus/test_k8s_monitoring_alerting.py`, and add the gauge to `SERVICE_SERIES` of `tests/telemetry/test_telemetry_instruments.py`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base for the new alert
- [x] 2.2 Add the alert `RoadmapServiceStateUnkept` at the end of the group `roadmap-service` in `k8s/monitoring/prometheus-values.yaml`: `max by (record) (devops_cli_service_state_unkept{job="roadmap-service"}) > 0`, `for: 15m`, severity warning, with the summary and the description that the promtool case pins, and a comment that names #4048
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py tests/telemetry/test_telemetry_instruments.py` passes

## 3. Document the gauge and the alert

Kind: documents. Reads: `k8s/README.md`. Changes: `k8s/README.md`.

- [x] 3.1 Add the row `RoadmapServiceStateUnkept` to the alert table of the section Roadmap service in `k8s/README.md`, next to the row `RoadmapServiceWebSearchRefused`. Say that the gauge lives in the memory of the process and a restart clears it. Name `devops_cli_service_state_unkept` in item 12 of the list of the Service
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py`

## 4. Chart the gauge on the dashboard

Kind: manifest. Reads: `k8s/monitoring/dashboards/devops-cli.json`, `tests/grafana/test_grafana_dashboards.py`. Changes: `k8s/monitoring/dashboards/devops-cli.json`, `tests/grafana/test_grafana_dashboards.py`.

- [x] 4.1 Add the panel "Service Unkept State Records" to the row "Roadmap Service" of `devops-cli.json` (it reads `max by (record)` of the gauge, below the row of four panels; the row "Alternatives Check" moves down 8 rows). The test of the row lists the panel, and the test that each `CONST_SERVICE_METRIC_` name has a query in the row passes
  - Verification: `$ uv run devops ci test tests/grafana/test_grafana_dashboards.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
