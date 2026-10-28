# Design

## Two paths, one job

The Service sends its series on two paths. k8s-monitoring's annotation autodiscovery scrapes the `/metrics` of the pod (the `devops_cli_service_*` series) and names the job after the pod's `app.kubernetes.io/name`. The OpenTelemetry collector writes the OTLP instruments (`devops_cli_github_*`, `devops_cli_ai_*`) and names the job after `OTEL_SERVICE_NAME`. The deployment sets both to `roadmap-service`, and `test_both_paths_name_the_roadmap_service_job` holds the two values together. So each `devops_cli_` selector has `job="roadmap-service"`. A workstation sends the same OTLP series with `job="devops-cli"`, and the old `kubernetes-pods` series of the Service have no samples after 2026-10-10. Neither counts.

kube-state-metrics gives the restarts and the replicas. Its selectors name `namespace="devops"` and the deployment `roadmap-service`, or the pods `roadmap-service-.+` and the container `service`.

## The rules

| Alert | Expression | For | Severity |
| :--- | :--- | :--- | :--- |
| `RoadmapServiceIdentityRefused` | `max by (identity) (devops_cli_service_identity_refused_total{job="roadmap-service"}) > 0` | 0m | critical |
| `RoadmapServiceGitHubThrottled` | `sum by (resource) (count_over_time(devops_cli_github_throttle_wait_seconds{job="roadmap-service"}[15m])) > 0` | 0m | critical |
| `RoadmapServiceJobsFailing` | `sum by (repo, lane) (increase(<errors>[1h]) + (<errors> offset 1h * 0 or min_over_time(<errors>[1h]))) >= 3`, where `<errors>` is `devops_cli_service_jobs_total{job="roadmap-service", result="error"}` | 0m | warning |
| `RoadmapServiceLaneStalled` | `time() - max by (repo, lane) (devops_cli_service_job_start_timestamp_seconds{job="roadmap-service"}) > 7200 and on () max(kube_deployment_status_replicas_available{namespace="devops", deployment="roadmap-service"}) > 0` | 10m | warning |
| `RoadmapServiceRestarted` | `max by (namespace, pod, container) (increase(kube_pod_container_status_restarts_total{namespace="devops", pod=~"roadmap-service-.+", container="service"}[1h])) > 0` | 0m | warning |
| `RoadmapServiceUnavailable` | `max by (namespace, deployment) (kube_deployment_status_replicas_unavailable{namespace="devops", deployment="roadmap-service"}) > 0` | 10m | warning |
| `RoadmapServiceGitHubRequestsHigh` | `sum(increase(devops_cli_github_requests_total{job="roadmap-service"}[1h])) > 450` | 0m | warning |
| `RoadmapServiceModelRequestsHigh` | `sum(increase(devops_cli_ai_requests_total{job="roadmap-service", cached!="true"}[1h])) > 352` | 0m | warning |

- **A refused identity.** The Service counts a refusal once and then starts no round until its pod restarts (capability `roadmap-service-limits`). The counter stays at 1 for as long, so the alert holds while the Service is stopped and clears when the restart removes the series.
- **A throttle.** The OTLP histogram gets a sample only when the Service sends a new observation, so a sample in 15 minutes is at least one throttle.
- **Failed jobs.** A job that fails 3 rounds in a row is suspended until its input changes. A lane whose error series is new reaches 1, 2 and 3 and then stays at 3. `increase()` gives about 2 over these samples, because it does not count the first value. `x offset 1h * 0` gives 0 for a series that was there an hour ago, and `or min_over_time(x[1h])` gives the first value of a new series, so the sum counts each error.
- **A stalled lane.** Each poll starts a round on each lane, every 5 minutes by default, and the Service sets the start timestamp when a round starts, also when the job of the round is suspended. With no available replica, the rule stays quiet, and `RoadmapServiceUnavailable` covers that case.
- **An unavailable replica.** The deployment uses the `Recreate` strategy, so a rollout has no available replica for some minutes. The rule waits 10 minutes.
- **Request volume.** 450 is 90% of the default `service.github_requests_per_hour` (500), and the test computes it from `DEFAULT_SERVICE_GITHUB_REQUESTS_PER_HOUR`. 352 is the number of #2472.
- **Annotations.** Each description ends with `(k8s/README.md, Roadmap service)`. A count prints with `printf "%.0f"`, because `increase()` gives a fraction by extrapolation.

## Rejected alternatives

- **`increase(devops_cli_service_identity_refused_total{job="roadmap-service"}[5m]) > 0`, as #2472 writes.** Rejected: the Service counts a refusal once, and the counter series starts at 1 with no zero sample before it (each error series of `devops_cli_service_jobs_total`, a counter of the same registry, starts at 1). `increase()` over one value, or over values that do not change, is 0, so the rule never fires.
- **`sum by (repo, lane) (increase(<errors>[1h])) >= 3`.** Rejected: at 2026-10-10T23:05:00Z, when the jobs of all 16 repository and lane pairs failed at each round, it found 1 pair, because the error series of 15 pairs started in that hour at 1. The expression of the rule found 16. In the unit tests, a new series that reaches 3 gives 2.05 with `increase()` alone.
- **The expression of #1392: errors in the hour `unless` a success in the hour, for 30 minutes.** Rejected for this change: after 3 failed rounds the job is suspended and its later rounds succeed (capability `roadmap-service-limits`, "Polls after the limit"), so a lane whose job always fails gets successes and the rule stays quiet. #1392 builds on this rule.
- **`histogram_count(increase(devops_cli_github_throttle_wait_seconds[15m])) > 0`.** Rejected: `increase()` needs two samples in its range, and one throttle is one sample.
- **`kube_deployment_status_replicas_ready`.** Rejected: neither the default allow list of the chart nor `metricsTuning.includeMetrics` keeps it, so it has no series. With no `minReadySeconds`, the available count is the ready count.
- **The recorded answers of the live Prometheus as a test fixture.** Rejected: 30 days of samples hold incidents for only 3 of the 8 rules (failed jobs, restarts and an unavailable replica), so the record cannot show that the other 5 fire. The promtool unit tests show each rule, and Feasibility keeps what the live queries showed.
- **A PromQL evaluation in Python.** Rejected: no maintained Python package evaluates PromQL, and promtool evaluates it with the engine of the server.
- **promtool from a container image.** Rejected: the CI runners and the devcontainer install tools from `tools.lock`, with a SHA-256 for each build, and no test starts a container.

## Tests

- `test_the_baseline_rule_set` lists the eight alerts with their severities.
- `test_the_roadmap_service_rules_watch_identity_jobs_lanes_pods_and_request_volume` pins each expression, wait and severity.
- `test_each_roadmap_service_rule_selects_only_the_service` holds each `devops_cli_` selector to `job="roadmap-service"` and each kube-state-metrics selector to the namespace and the deployment or its pods.
- `test_both_paths_name_the_roadmap_service_job` holds the pod's `app.kubernetes.io/name`, `OTEL_SERVICE_NAME` and the scrape annotations of the deployment.
- `test_the_roadmap_service_rules_read_kube_state_metrics_that_the_chart_keeps` checks the three kube-state-metrics series against the allow list and `includeMetrics`.
- `test_every_alert_rule_selects_only_series_the_stack_serves` reads the six `devops_cli_` names from `CONST_SERVICE_METRIC_*` and `instruments.py`.
- `test_each_roadmap_service_alert_points_to_its_step_in_the_readme` checks each description and the README part "Alerts".
- `test_promtool_accepts_every_alert_rule` runs `promtool check rules` over every alert rule.
- `test_each_roadmap_service_rule_fires_on_a_sample_and_stays_quiet_on_a_normal_series` runs `promtool test rules` over the unit tests, and checks that they test each alert of the group.
- `test_the_test_job_installs_the_pinned_promtool_before_the_gate` checks the CI step.
