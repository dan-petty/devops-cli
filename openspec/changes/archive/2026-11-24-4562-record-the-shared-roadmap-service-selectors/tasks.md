# Tasks

## 1. Add the recording group, its promtool cases and its checks

Kind: manifest. Reads: `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_recording_tests.yaml` (new), `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [x] 1.1 The case `Each recording rule produces its series and stays quiet on a series of another job` of `tests/fixtures/prometheus_rules/roadmap_service_recording_tests.yaml` fails `test_each_unit_tested_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series` while the group `roadmap-service-recording` is absent from `k8s/devops/monitoring/prometheus-rules-values.yaml`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [x] 1.2 Add the group `roadmap-service-recording` to `serverFiles.devops_cli_alerting_rules.yml` of `k8s/devops/monitoring/prometheus-rules-values.yaml` with `repo_lane_row:devops_cli_service_jobs_total:increase1h` as `sum by (repo, lane, row, result) (increase(devops_cli_service_jobs_total{job=~"roadmap-service|roadmap-.+"}[1h]))`, `repo_row_class:devops_cli_service_job_suspended:max` as `max by (repo, row, class) (devops_cli_service_job_suspended{job=~"roadmap-service|roadmap-.+"})` and `service:devops_cli_service_budget_requests_per_limit:ratio` as the sum of `devops_cli_service_budget_spent_requests` divided by the sum of `devops_cli_service_budget_limit_requests`, both with the same job matcher. Add `tests/fixtures/prometheus_rules/roadmap_service_recording_tests.yaml` with `rule_files: [roadmap-service-recording.rules.yaml]`, `evaluation_interval: 1m` and one `promql_expr_test` case for each rule, beside a series of another job. In `tests/prometheus/test_k8s_monitoring_alerting.py` add `ROADMAP_SERVICE_RECORDING_GROUP`, its case-file path and its entry in `RULE_GROUP_TESTS`; import `CONST_SERVICE_METRIC_BUDGET_SPENT` and add it with the three record names to `SERVED_SERIES`; read `rule.get("alert")` in `test_the_promtool_files_of_a_group_test_every_alert_of_the_group` and in `test_each_unit_tested_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series`; add `test_each_recording_rule_name_has_three_parts` and `test_each_covered_row_work_selector_has_one_recording_rule`
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 2. Move the three row work alerts to the recorded series

Kind: manifest. Reads: `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`. Changes: `k8s/devops/monitoring/prometheus-rules-values.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [x] 2.1 The case `A row that stays suspended for 3 hours fires with its class; a row that runs again and another job do not count` of `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` fails `test_each_unit_tested_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series` while `RoadmapServiceRowSuspended` reads the raw gauge and the case supplies the recorded series
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [x] 2.2 Change `RoadmapServiceJobsFailing`, `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceRowSuspended` in `k8s/devops/monitoring/prometheus-rules-values.yaml` to read `repo_lane_row:devops_cli_service_jobs_total:increase1h`, `service:devops_cli_service_budget_requests_per_limit:ratio` and `repo_row_class:devops_cli_service_job_suspended:max` of the group `roadmap-service-recording`. Supply those recorded series as input series in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, in the case of each of the three alerts, and keep the summary of the budget alert as `{{ $value | humanizePercentage }}`. Add `test_each_row_work_alert_reads_a_recorded_series` to `tests/prometheus/test_k8s_monitoring_alerting.py`, which refuses a `job="roadmap-service"` selector in the three alerts and a series that no rule of `roadmap-service-recording` records
  - Verification: `$ uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes

## 3. Name the recording group in the monitoring docs

Kind: other. Reads: `k8s/README.md`, `docs/CLUSTER.md`, `k8s/devops/monitoring/prometheus-rules-values.yaml`. Changes: `k8s/README.md`, `docs/CLUSTER.md`.

- [x] 3.1 Name the group `roadmap-service-recording` and its three recorded series in the paragraph on the product rule file of `k8s/README.md` and in the rule-group paragraph of `docs/CLUSTER.md`, and say that the row work alerts read the recorded series while the router health selectors keep `job="roadmap-service"`. Change the rows of `RoadmapServiceJobsFailing`, `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceRowSuspended` in both alert tables to the recorded series, keeping the cell count of each row, and add the case file to the list of promtool case files in `docs/CLUSTER.md`
  - Verification: `$ uv run devops ci docs` passes
- [x] 3.2 Edit `k8s/README.md` and `docs/CLUSTER.md` to name the `roadmap-service-recording` group, its three recorded series and its case file. Update `src/devops_cli/telemetry/instruments.py`
  - Verification: `$ uv run devops ci docs` passes

## Criteria

- Group 2: Each "row work" alert reads a recorded series, and its promtool test passes.
- Group 1: Rule names follow the `level:metric:operations` form.
- Group 1: The promtool tests stay within the time budget of their check.
