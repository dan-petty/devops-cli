# Tasks

## 1. Zero series and the repo label of the failure counter

Reads: `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/telemetry/metrics.py`, `src/devops_cli/server/service.py`, `tests/prometheus/test_implement_failure_labels.py`. Changes: `src/devops_cli/telemetry/metrics.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `src/devops_cli/server/counter_series.py`, `tests/prometheus/test_implement_failure_labels.py`.

- [ ] 1.1 Add a test to `tests/prometheus/test_implement_failure_labels.py` that starts the Service with two repositories and asserts that the failure counter exists at 0 for each of the 19 classes and each repository
  - Verification: `uv run devops ci test tests/prometheus/test_implement_failure_labels.py` fails on the base
- [ ] 1.2 Add a test to `tests/prometheus/test_implement_failure_labels.py` that asserts that every value of the label `repo` of the failure counter is a value of `service.repos`
  - Verification: `uv run devops ci test tests/prometheus/test_implement_failure_labels.py` fails on the base
- [ ] 1.3 Add the function that creates the bounded label sets of the Service counters at zero in `src/devops_cli/server/counter_series.py`, call it at the start of the Service, and pass `repo` from `run_implement_round` to the failure count of `src/devops_cli/roadmap/implement_submit.py`
  - Verification: `uv run devops ci test tests/prometheus/test_implement_failure_labels.py` passes

## 2. The job counter carries the row

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `tests/roadmap/test_roadmap_run.py`. Changes: `tests/telemetry/test_service_counter_series.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`.

- [ ] 2.1 Add `tests/telemetry/test_service_counter_series.py` with a test that runs one row of a lane and asserts that the job counter holds the labels `repo`, `lane`, `row` and `result`, and that each row of a lane has its own count
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [ ] 2.2 Count each row of a lane in the roadmap run with its result, and remove the per-batch count of the worker in `src/devops_cli/server/service.py`. Count each scoped update with the name of its job
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py tests/roadmap/test_roadmap_run.py` passes
- [ ] 2.3 Prime the job counter for each repository, lane, row and result, and the job seconds counter for each repository and lane, in `src/devops_cli/server/counter_series.py`
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` passes

## 3. The webhook counter starts at zero

Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/server/counter_series.py`. Changes: `src/devops_cli/server/counter_series.py`, `tests/telemetry/test_service_counter_series.py`.

- [ ] 3.1 Add a test to `tests/telemetry/test_service_counter_series.py` that asserts that the webhook counter exists at 0 for each provider, each declared event with `other`, and each outcome
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [ ] 3.2 Prime the webhook counter in `src/devops_cli/server/counter_series.py` from the declared providers and their events
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` passes

## 4. The promtool cases hold the rules and the zero series

Reads: `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/monitoring/prometheus-values.yaml`. Changes: `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml`, `k8s/monitoring/prometheus-values.yaml`.

- [ ] 4.1 Add a promtool case `pod_change_gives_true_total` to `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`. Its series of the failure counter start at 0 in each pod, and the case asserts the sum of `increase()` over a pod change
  - Verification: `promtool test rules tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` passes
- [ ] 4.2 Add a promtool case to `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml` that fires `RoadmapServiceWebhooksRejected` on a rejected series that starts at 0
  - Verification: `promtool test rules tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml` passes
- [ ] 4.3 Remove the #2505 workaround terms of `RoadmapServiceWebhooksRejected` and `RoadmapServiceSelfDeliveriesHigh` from `k8s/monitoring/prometheus-values.yaml`, and replace the stale comment at lines 670-673 with the scrape behavior. Keep the OTLP terms
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes and `promtool test rules tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml` passes

## 5. The documents state the scrape behavior and the labels

Reads: `docs/TELEMETRY.md`, `k8s/README.md`. Changes: `docs/TELEMETRY.md`, `k8s/README.md`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [ ] 5.1 Add a test to `tests/prometheus/test_k8s_monitoring_alerting.py` that asserts that the action text of `RoadmapServiceGitHubRequestsHigh` in `k8s/README.md` does not say to lower the budget
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [ ] 5.2 Rewrite the action text of `RoadmapServiceGitHubRequestsHigh` in `k8s/README.md` without the word to lower the budget, rewrite `docs/TELEMETRY.md` lines 19-32 to state the scrape behavior and the labels, state the class count of 19 in `k8s/README.md`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes and `uv run devops ci docs` passes

## Workflow follow-up

- Open item: agree the label `repo` of `devops_cli_service_implement_failures_total` with #3069 before this change lands. The issue says that #3069 reuses the label `class`.
- Open item: check the live series with a Prometheus query after the deploy. This change runs no live query.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
