# Design

## Context

The dashboard `devops-cli Telemetry` reads the series that devops-cli sends over OTLP. The Service also has series on its `/metrics` route, which Prometheus scrapes. All of the series carry the `job` label: `devops-cli` for a workstation, `devops-cli-job` for a cluster Job, and `roadmap-service` for the Service.

## Decisions

- **Each Prometheus query filters by `$job`.** The matcher `job=~"$job"` comes first in each selector. With All, the variable gives `.*`, so the panels show what they show now. The logs panel reads Loki, which has no such label, so it stays as it is.
- **The Service row also filters by `$job`.** One rule holds for each query of the dashboard. Only the Service sends these series, so All and `roadmap-service` give the same values.
- **The variables `command` and `sub_command` filter by `$job`.** So their lists show only the values of the selected job. The variable `job` is first in the list, because a Grafana variable reads only the variables before it.
- **`job` reads `label_values({__name__=~"devops_cli_command_total|devops_cli_github_requests_total"}, job)`.** The list follows the time range, so a job shows only if it sent one of the series in that range. A workstation or a Job adds to the command series when a command ends. The Service adds to it only when `devops serve` stops, but it adds to the GitHub series as it works. The issue names the command series only, and that list usually does not offer `roadmap-service` at the default range of 1 hour.
- **The row reads a scraped gauge with `last_over_time(<series>[5m])`.** The dashboard tests ask each gauge to go through `last_over_time`. A window of 5 minutes equals the lookback of a plain selector, so a panel keeps its history.
- **The row reads the identity counter by its value.** The label set of `devops_cli_service_identity_refused_total` starts with the first refusal, so `increase()` loses that count. The alert `RoadmapServiceIdentityRefused` reads the value for the same reason.
- **The budget sentence goes beside the steps that change the budget** in `k8s/README.md`, because a reader of the budget reads this text.

## Rejected alternatives

- **A separate dashboard for the Service.** The alerts of the Service already send the reader to `devops-cli Telemetry`, and the GitHub panels that the Service needs are on it.
- **A fixed `job="roadmap-service"` in the Service row.** It gives the same values as `$job` with All, because the live `devops_cli_service_*` series have only this value. It adds a second rule for one dashboard.
- **`label_values(devops_cli_command_total, job)` for the variable.** The value `roadmap-service`, which the steps of two alerts name, is not in the list in most hours.
- **`label_values(devops_cli_github_requests_total, job)` for the variable.** A workstation or a Job that ran commands and sent no GitHub request in the range is not in the list.
- **`label_values({__name__=~"devops_cli_.+"}, job)` for the variable.** The live answer also holds `kubernetes-pods`, an old scrape job that sends nothing now.
- **Make the Jobs count in the budget.** A Job pod has an `emptyDir` home, so the count needs a ledger across pods. The issue does not ask for one.
- **A second GitHub App for the Jobs.** ADR 0015 makes the Service and the Jobs act as one App, and a second App adds a second key to manage.
