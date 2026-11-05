# Tasks

## 1. Zero series and the repo label of the failure counter

Reads: `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/telemetry/metrics.py`, `src/devops_cli/server/service.py`, `tests/roadmap/test_roadmap_implement_submit.py`. Changes: `src/devops_cli/telemetry/metrics.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/server/service.py`, `src/devops_cli/server/counter_series.py`, `tests/telemetry/test_service_counter_series.py`, `tests/roadmap/test_roadmap_implement_submit.py`.

- [x] 1.1 Add a test to `tests/telemetry/test_service_counter_series.py` that builds the Service manager with two repositories and asserts that the failure counter exists at 0 for each of the 19 classes and each repository
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [x] 1.2 Add a test to `tests/telemetry/test_service_counter_series.py` that asserts that every value of the label `repo` of the failure counter is a value of `service.repos`, and change the counter assertions of `tests/roadmap/test_roadmap_implement_submit.py` to read the label `repo`
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py tests/roadmap/test_roadmap_implement_submit.py` fails on the base
- [x] 1.3 Add the function that creates the bounded label sets of the Service counters at zero in `src/devops_cli/server/counter_series.py`, call it when the Service manager is built, and pass `repo` from `run_implement_round` to the failure count of `src/devops_cli/roadmap/implement_submit.py`
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py tests/roadmap/test_roadmap_implement_submit.py` passes

## 2. The job counter carries the row

Reads: `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `tests/roadmap/test_roadmap_run.py`. Changes: `tests/telemetry/test_service_counter_series.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/service.py`, `src/devops_cli/server/counter_series.py`.

- [x] 2.1 Add a test to `tests/telemetry/test_service_counter_series.py` that asserts that the job counter holds the labels `repo`, `lane`, `row` and `result`, and that the row `metrics` of the status lane exists at 0 for `result` `success`. Add a test to `tests/roadmap/test_roadmap_run.py` that runs a lane with one row that fails, and asserts that each row counts its own job under its result
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [x] 2.2 Count each row of a lane in the roadmap run with its result, and remove the per-batch count of the worker in `src/devops_cli/server/service.py`. Count each scoped update with the name of its job
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py tests/roadmap/test_roadmap_run.py` passes
- [x] 2.3 Prime the job counter for each repository, lane, row and result, and the job seconds counter for each repository and lane, in `src/devops_cli/server/counter_series.py`
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` passes

## 3. The webhook counter starts at zero

Reads: `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/server/counter_series.py`. Changes: `src/devops_cli/server/routes/webhooks.py`, `tests/telemetry/test_service_counter_series.py`, `tests/server/test_server_service.py`.

- [x] 3.1 Add a test to `tests/telemetry/test_service_counter_series.py` that asserts that the webhook counter exists at 0 for each provider, each declared event with `other`, and each outcome
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [x] 3.2 Prime the webhook counter in `src/devops_cli/server/counter_series.py` from the declared providers and their events
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` passes

## 4. The promtool cases hold the rules and the zero series

Reads: `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/monitoring/prometheus-values.yaml`. Changes: `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml`, `k8s/monitoring/prometheus-values.yaml`.

- [x] 4.1 Add a promtool case `pod_change_gives_true_total` to `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`. Its series of the failure counter start at 0 in each pod, and the case asserts the sum of `increase()` over a pod change
  - Verification: `promtool test rules tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` passes
- [x] 4.2 Edit the first case of `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml`, so that its rejected series with the event `other` starts at 0 and the case fires `RoadmapServiceWebhooksRejected` at 34 minutes. The case replaces the #2505 gap with the zero samples and adds no new case
  - Verification: `promtool test rules tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml` passes
- [x] 4.3 Remove the #2505 workaround terms of `RoadmapServiceWebhooksRejected` and `RoadmapServiceSelfDeliveriesHigh` from `k8s/monitoring/prometheus-values.yaml`, and replace the stale comment at lines 670-673 with the scrape behavior. Keep the OTLP terms
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes and `promtool test rules tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml` passes

## 5. The documents state the scrape behavior and the labels

Reads: `docs/TELEMETRY.md`, `k8s/README.md`. Changes: `docs/TELEMETRY.md`, `k8s/README.md`, `tests/prometheus/test_k8s_monitoring_alerting.py`.

- [x] 5.1 Add a test to `tests/prometheus/test_k8s_monitoring_alerting.py` that asserts that the action text of `RoadmapServiceGitHubRequestsHigh` in `k8s/README.md` does not say to lower the budget
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the base
- [x] 5.2 Rewrite the action text of `RoadmapServiceGitHubRequestsHigh` in `k8s/README.md` without the word to lower the budget, rewrite `docs/TELEMETRY.md` lines 19-32 to state the scrape behavior and the labels, state the class count of 19 in `k8s/README.md`, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes and `uv run devops ci docs` passes

## 6. The trigger and chat counters start at zero

Reads: `src/devops_cli/server/counter_series.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/server/service.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/server/counter_series.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/docs/generator.py`, `docs/TELEMETRY.md`, `k8s/README.md`, `tests/telemetry/test_service_counter_series.py`.

- [x] 6.1 Add tests to `tests/telemetry/test_service_counter_series.py` that assert that the trigger counter exists at 0 for each repository with the sources `webhook` and `poll`, and that the chat counter exists at 0 for each result `usage`, `status`, `unknown_repo` and `error`
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [x] 6.2 Prime the trigger counter and the chat counter in `src/devops_cli/server/counter_series.py`, define the chat command constants in `src/devops_cli/config/constants.py`, and use them in the chat route of `src/devops_cli/server/routes/webhooks.py`
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py tests/server/test_mattermost_slash_command.py` passes
- [x] 6.3 State in `src/devops_cli/docs/generator.py`, the source of `docs/TELEMETRY.md`, and in `k8s/README.md` that the identity counter is the one counter whose label set does not start at zero, and regenerate `docs/TELEMETRY.md` with `uv run devops docs generate --no-sync-readme`
  - Verification: `uv run devops ci docs` passes

## 7. The job failure alert reads each row

Reads: `k8s/monitoring/prometheus-values.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `src/devops_cli/server/service.py`. Changes: `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `k8s/monitoring/prometheus-values.yaml`, `k8s/README.md`.

- [x] 7.1 Add a promtool case to `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` in which the row `implement` fails each round while the row `metrics` of its lane succeeds, label the job series of the other cases with a row, and pin the rule in `tests/prometheus/test_k8s_monitoring_alerting.py`
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` fails on the rule that joins on the lane
- [x] 7.2 Group and join `RoadmapServiceJobsFailing` on `repo`, `lane` and `row`, and name the row in its summary, in `k8s/monitoring/prometheus-values.yaml`. Keep the fields of its Loki query
  - Verification: `uv run devops ci test tests/prometheus/test_k8s_monitoring_alerting.py` passes
- [x] 7.3 State in the two alert tables of `k8s/README.md` that the alert reads each row
  - Verification: `uv run devops ci docs` passes

## 8. A stop is no failed row

Reads: `src/devops_cli/exceptions/roadmap.py`, `src/devops_cli/roadmap/run.py`. Changes: `src/devops_cli/config/constants.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/counter_series.py`, `tests/roadmap/test_roadmap_run.py`, `tests/telemetry/test_service_counter_series.py`, `k8s/README.md`.

- [x] 8.1 Add tests to `tests/roadmap/test_roadmap_run.py` that assert that a row and a scoped update that the stop of the Service ends count under `stopped` and a scoped update that fails counts under `error`, and a test to `tests/telemetry/test_service_counter_series.py` that asserts that a row exists at 0 for each result
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py tests/telemetry/test_service_counter_series.py` fails on the count that reads only `error`
- [x] 8.2 Count a row and a scoped update under the result of their error in `src/devops_cli/roadmap/run.py`, and prime the result `stopped` in `src/devops_cli/server/counter_series.py`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_run.py tests/telemetry/test_service_counter_series.py` passes
- [x] 8.3 State the three results of the job counter in `k8s/README.md`
  - Verification: `uv run devops ci docs` passes

## 9. The budget hold counter starts at zero

Reads: `src/devops_cli/telemetry/metrics.py`. Changes: `tests/telemetry/test_service_counter_series.py`, `src/devops_cli/server/counter_series.py`.

- [x] 9.1 Add a test to `tests/telemetry/test_service_counter_series.py` that asserts that the budget hold counter exists at 0 with no label
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` fails on the base
- [x] 9.2 Prime the budget hold counter in `src/devops_cli/server/counter_series.py`
  - Verification: `uv run devops ci test tests/telemetry/test_service_counter_series.py` passes

## Workflow follow-up

- A round that fails before its first row counts no job, so `RoadmapServiceJobsFailing` does not read it: #3666.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
