# Proposal

## Why

Issue #2479: no dashboard shows the `devops_cli_service_*` series, and no panel of `devops-cli.json` filters by `job`. The panel GitHub Requests by Resource adds the requests of all jobs, but the alert `RoadmapServiceGitHubRequestsHigh` sends the reader to it. `k8s/README.md` says that the Service and the cluster Jobs act as one App, and no text says what that means for the budget.

## What Changes

- Add the row "Roadmap Service" to `k8s/monitoring/dashboards/devops-cli.json`. Its panels read each `devops_cli_service_*` series.
- Add the query variable `job`, and make each Prometheus query of the dashboard filter by `$job`. The variables `command` and `sub_command` also filter by `$job`.
- Tell the reader of the alerts `RoadmapServiceGitHubRequestsHigh` and `RoadmapServiceGitHubThrottled` to set the variable `Job` to `roadmap-service`.
- Say in `k8s/README.md` that the Jobs act as the same App and do not count in `service.github_requests_per_hour`.
- A dashboard is a manifest that a consumer reads, so the change carries spec deltas.
- This change fits one pull request.

The work that this issue held before the split is out of scope: the Service's own gateway key is #3685, blocked by #1635, and #2500 delivered the one model retry.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `command-telemetry`: the `job` variable, and the variables and the queries of the dashboard filter by it.
- `github-api-metrics`: the queries of the row "GitHub API" filter by `$job`.
- `roadmap-service-counters`: the row "Roadmap Service" charts the series of the Service.

## Feasibility

The premise holds. I checked each point on 2026-11-05, against origin/main at 05544abc and against the live Prometheus of the cluster.

- `git grep` finds no `devops_cli_service_` in `k8s/monitoring/dashboards/`. The dashboard has only the variables `command` and `sub_command`.
- `count by (job) (last_over_time(devops_cli_command_total[7d]))` gives the values `devops-cli`, `devops-cli-job` and `roadmap-service`. So this series can give the values of the variable.
- `label_values` on `devops_cli_service_.*` gives `job="roadmap-service"` only. Prometheus holds each series that `src/devops_cli/config/constants.py` names, except `devops_cli_service_identity_refused_total`, which starts at the first refusal, and `devops_cli_service_chat_commands_total`, which had no series in the live data at that time.
- `sum by (job) (last_over_time(devops_cli_github_requests_total[7d]))` has a value for each of the three jobs, so the Jobs send their own requests under `job="devops-cli-job"`.
- Only `src/devops_cli/server/service.py` makes a `RequestBudget`, and its record is on the Service's volume. `k8s/devops/cronjob.yaml` and `k8s/devops/cronjob-runner.yaml` give the Job pods an `emptyDir` home. So the Jobs do not count in the budget.

## Existing Tool Considered

Grafana dashboard variables and Prometheus label filters cover the need. The dashboard already uses both for `command` and `sub_command`. The change builds nothing and deletes no internal code.
