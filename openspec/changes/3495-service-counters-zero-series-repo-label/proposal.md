# Proposal

## Why

Issue #3495 reports that the Service counters give a false picture. The counters come from the `/metrics` scrape, and each release starts a new pod. A label set has no series until its first increment, so `increase()` loses the first count of each new label set. The failure counter `devops_cli_service_implement_failures_total` also has no `repo` label, so one series mixes all repositories. This change fits one pull request.

## What Changes

- When the Service starts, it creates each bounded label set of its counters at zero: each failure class for each repository of `service.repos`, each repository, lane, row and result of `devops_cli_service_jobs_total`, each repository and lane of `devops_cli_service_job_seconds_total`, each provider, declared event and outcome of `devops_cli_service_webhook_deliveries_total`, each repository and source of `devops_cli_service_triggers_total`, and each result of the `/roadmap` chat command on `devops_cli_service_chat_commands_total`. The identity counter `devops_cli_service_identity_refused_total` is left out (see design.md).
- `devops_cli_service_implement_failures_total` gets the label `repo`.
- `devops_cli_service_jobs_total` gets the label `row`. The roadmap run counts each row of a lane with its result. The worker no longer counts a whole lane batch.
- The alert expressions of `RoadmapServiceWebhooksRejected` and `RoadmapServiceSelfDeliveriesHigh` lose their #2505 workaround terms. The OTLP alert expressions keep theirs.
- Promtool cases prove the true total over a pod change, and prove that the webhook alerts hold without the workaround.
- `docs/TELEMETRY.md` and `k8s/README.md` state the scrape behavior and the labels. The action text of `RoadmapServiceGitHubRequestsHigh` no longer says to lower the budget. The class count of the Service changes from 17 to 19.

## Capabilities

### New Capabilities

- `roadmap-service-counters`: The label sets of the Service counters, which the Service creates at zero when it starts, and the labels that the counters of the Service carry.

### Modified Capabilities

- `roadmap-implement-job`: The failure counter adds the label `repo` to the label `class`.

## Impact

- Code: `src/devops_cli/telemetry/metrics.py`, `src/devops_cli/server/service.py`, `src/devops_cli/server/counter_series.py`, `src/devops_cli/roadmap/implement_submit.py`, `src/devops_cli/roadmap/run.py`, `src/devops_cli/server/routes/webhooks.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/docs/generator.py`.
- Monitoring: `k8s/monitoring/prometheus-values.yaml`.
- Tests: `tests/prometheus/test_implement_failure_labels.py`, `tests/telemetry/test_service_counter_series.py`, `tests/prometheus/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`, `tests/fixtures/prometheus_rules/roadmap_service_webhooks_tests.yaml`.
- Documents: `docs/TELEMETRY.md`, `k8s/README.md`.
- The change adds no dependency.

## Feasibility

- The failure counter increments with the label `class` only. This is confirmed by reading `src/devops_cli/roadmap/implement_submit.py` at origin/main, where `GLOBAL_METRICS.increment_counter(CONST_SERVICE_METRIC_IMPLEMENT_FAILURES, labels={"class": failure.value})` runs.
- The jobs counter has the labels `repo`, `lane` and `result`, and no `row`. This is confirmed by reading `src/devops_cli/server/service.py` at origin/main, where the worker increments it with `{**self._labels, "result": result}`.
- A labelled counter emits no sample until a child exists. This is confirmed by a probe with prometheus_client 0.26.0 in the devcontainer: the counter with the labels `class` and `repo` emitted no line, and after `.labels("oom", "example/app")` it emitted `probe_total{class="oom",repo="example/app"} 0.0`.
- The enum `FailureClass` in `src/devops_cli/roadmap/failure.py` has 19 members. `k8s/README.md:630` says 17. This is confirmed by reading both files at origin/main.
- The action text of `RoadmapServiceGitHubRequestsHigh` in `k8s/README.md:705` says "Lower the budget or remove a repository". This is confirmed by reading the file at origin/main.
- `k8s/monitoring/prometheus-values.yaml:23` enables `created-timestamp-zero-ingestion`. The stale comment at lines 670-673 says that neither path has a zero sample. This is confirmed by reading the file at origin/main.
- The upstream statement that start-timestamp injection covers only PrometheusProto and OpenMetrics 1.0.0 scrapes is recorded from the issue research and is not checked again here. The design does not depend on it.
- The live evidence table of the issue is not checked. No live Prometheus query ran in this change.

## Existing Tool Considered

The open tool `prometheus_client` covers the zero series: calling `.labels(...)` at start creates the child at 0, and the text exposition shows it (see Feasibility). The open tool `promtool` checks the rules and runs their unit tests. Both are present, so the change adds no code for the exposition format. The change deletes these internal parts: the per-batch count of `devops_cli_service_jobs_total` in the worker (`src/devops_cli/server/service.py`), the two #2505 workaround terms of the webhook alerts in `k8s/monitoring/prometheus-values.yaml`, and the stale comment at lines 670-673 of the same file. The module `src/devops_cli/server/counter_series.py` has 95 lines, and its function `prime_service_counters` has 48 lines. The function holds the label sets of the counters, and the change adds no custom metric type.
