# Proposal

## Why

Issue #2472: no Prometheus rule selects a `devops_cli_` series, so the roadmap Service can fail, stop or send too many GitHub requests, and no alert fires. On 2026-10-11 GitHub suspended the identity of the Service, and the Service logged 551 job errors with no alert. When GitHub refuses the identity, the Service stops all rounds, but `/healthz` stays healthy. The Service goes back online as GitHub App `devops-cli-service`.

## What Changes

- `k8s/monitoring/prometheus-values.yaml` gets the rule group `roadmap-service`, after `homelab-services`, with eight alerts. The critical alerts are `RoadmapServiceIdentityRefused` and `RoadmapServiceGitHubThrottled`. The warning alerts are `RoadmapServiceJobsFailing`, `RoadmapServiceLaneStalled`, `RoadmapServiceRestarted`, `RoadmapServiceUnavailable`, `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceModelRequestsHigh`.
- Each selector of a `devops_cli_` series has `job="roadmap-service"`. Each kube-state-metrics selector has `namespace="devops"` and the deployment `roadmap-service` or its pods.
- Each description points to "Roadmap service" in `k8s/README.md`. Its new part "Alerts" says when each alert fires and what to do.
- `tools.lock` pins promtool 3.15.0, the version of the Prometheus server of the cluster. The CI test job installs it before the gate.
- `tests/test_k8s_monitoring_alerting.py` pins each rule and holds each selector to the job, namespace and deployment of the Service. It runs `promtool check rules` over every alert rule, and `promtool test rules` over the unit tests in `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml`. In these unit tests, each alert fires on a sample series and stays quiet on a normal series. The two promtool tests skip where promtool is not installed.
- `tests/test_workflow_contracts.py` checks that the test job installs the pinned promtool before the gate.
- Four expressions are not the ones that #2472 writes. Design gives the evidence:
  - `RoadmapServiceIdentityRefused` fires while the refusal counter is above 0, not on `increase(...[5m]) > 0`. The counter starts at 1, so `increase()` does not see the refusal.
  - `RoadmapServiceJobsFailing` adds the first value of an error series that starts in the hour, which `increase()` does not count.
  - `RoadmapServiceLaneStalled` reads the available replicas, not the ready replicas. The chart keeps only the available count, and with no `minReadySeconds` the two counts are equal.
  - `RoadmapServiceModelRequestsHigh` does not count a request that the cache answered (`cached="true"`), because that request does not go to a model.
- The change alters a manifest, so it carries a spec delta for the new capability `roadmap-service-alerts`.
- The change fits in one pull request.

## Capabilities

### New Capabilities

- `roadmap-service-alerts`: the alerts that watch the identity, the jobs, the lanes, the pod and the request volume of the roadmap Service.

### Modified Capabilities

None.

## Impact

- Manifest: `k8s/monitoring/prometheus-values.yaml`. Argo CD's `prometheus` Application applies it after the merge, and the Prometheus server loads the rules again. The deployment of the Service is at `replicas: 0`, so the series of the Service get no samples, and no rule of the group fires until the Service runs again.
- Delivery: no alert leaves the cluster until the Secret `monitoring/alertmanager-webhook` exists. Creating it is a step for the owner, who chose Mattermost as the route for the alerts (#1391, #1392).
- Related: #1392 plans a rule with the same name, `RoadmapServiceJobsFailing`, and another expression (every round of a repository and lane failed for an hour). When #1392 is built, it changes this rule and adds no second rule with that name.
- Tools: `tools.lock` gets promtool. The post-create step of the devcontainer installs it with the other tools. The CI test job downloads the Prometheus release archive (112 MB) in each run.
- Tests: `tests/test_k8s_monitoring_alerting.py`, `tests/fixtures/prometheus_rules/roadmap_service_tests.yaml` and `tests/test_workflow_contracts.py`.

## Feasibility

Checked on 2026-10-28 against the code at `origin/main` 08d70ca6, and read-only, through the Grafana MCP tools, against the Prometheus server of the cluster (`prometheus_build_info`: version 3.15.0) with its 30 days of samples.

- **Names and labels.** `devops_cli_service_identity_refused_total{identity}`, `devops_cli_service_jobs_total{repo, lane, result}` and `devops_cli_service_job_start_timestamp_seconds{repo, lane}` are series of the `/metrics` of the Service (`CONST_SERVICE_METRIC_*`, recorded in `src/devops_cli/server/service.py`). `devops_cli_github_requests_total{resource}`, `devops_cli_github_throttle_wait_seconds{resource}` and `devops_cli_ai_requests_total{cached, ...}` are OTLP instruments (`src/devops_cli/telemetry/instruments.py`). The GitHub rate limiter (`src/devops_cli/github/rate_limiter.py`) records the two GitHub instruments.
- **Series in Prometheus.** Prometheus holds `devops_cli_service_jobs_total`, `devops_cli_service_job_start_timestamp_seconds` and `devops_cli_ai_requests_total` with `job="roadmap-service"` and the labels above. `devops_cli_github_requests_total` has series only with `job="devops-cli"`, and `devops_cli_github_throttle_wait_seconds` and `devops_cli_service_identity_refused_total` have no series. #2354 and #2406 added these three on 2026-10-27 and 2026-10-28, after the Service stopped. Their names and labels come from the code.
- **The job of each path.** The scraped series have `instance="<pod-ip>:8000"` and `container="service"`. k8s-monitoring's annotation autodiscovery names their job after the pod's `app.kubernetes.io/name` (`k8s/monitoring/k8s-monitoring-values.yaml`). The OTLP series have `instance="<pod-name>"`, and the OpenTelemetry collector names their job after `OTEL_SERVICE_NAME`. Both jobs are `roadmap-service`. The `job="kubernetes-pods"` series of the Service stop on 2026-10-10, when the `job="roadmap-service"` series start: since #1130 the `kubernetes-pods` job of the server keeps only namespace `otel`. A workstation sends the same OTLP series with `job="devops-cli"`.
- **First samples.** Each `result="error"` series of `devops_cli_service_jobs_total` starts at 1, and each of the 25 `devops_cli_ai_requests_total` series of the Service starts above 0. A series has no zero sample before its first count, so `increase()` does not count its first value. At 2026-10-10T23:05:00Z, when the jobs of all 16 repository and lane pairs failed at each round, `sum by (repo, lane) (increase(<errors>[1h])) >= 3` found 1 pair, and the expression of `RoadmapServiceJobsFailing` found 16. At 2026-10-10T20:00:00Z, when the 16 pairs ran normally, `RoadmapServiceJobsFailing` and `RoadmapServiceLaneStalled` found none.
- **Histogram samples.** The OTLP instruments send deltas, and each histogram is exponential (`src/devops_cli/telemetry/tracer.py`). Prometheus stores `devops_cli_github_throttle_wait_seconds` as a native histogram and gets a sample only when the Service sends a new observation: in one day, `devops_cli_command_duration_seconds` got 4865 samples for about 5344 observations.
- **kube-state-metrics.** The default allow list of the chart keeps `kube_deployment_status_replicas_available` and `kube_pod_container_status_restarts_total`, and `metricsTuning.includeMetrics` keeps `kube_deployment_status_replicas_unavailable`. Neither keeps `kube_deployment_status_replicas_ready`. The deployment sets no `minReadySeconds`.
- **The 352 threshold.** No setting or constant of the code gives 352. It is the number that #2472 gives. In 30 days, no hour had more than 47 model requests of the Service.
- **promtool.** Prometheus publishes promtool in each release archive. The SHA-256 of each of the four archives of v3.15.0 is the `digest` of its release asset and is in the `sha256sums.txt` of the release.

## Existing Tool Considered

The alert rules of the cluster are in `serverFiles.alerting_rules.yml` of the prometheus-community `prometheus` chart (`k8s/argocd/apps/prometheus.yaml`), not in a PrometheusRule of kube-prometheus-stack as #2472 says, and this change adds one group there. promtool is the tool that Prometheus publishes to check rule files and to unit-test rules, and #2472 names `promtool test rules`. The change builds no code and deletes no internal code.
