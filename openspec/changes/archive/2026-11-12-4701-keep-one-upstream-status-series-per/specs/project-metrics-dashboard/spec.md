## MODIFIED Requirements

### Requirement: A gauge panel shows the latest value in the time range
Each gauge panel of the project dashboard, other than the upstream status panels, SHALL read `last_over_time(<metric>[$__range])`, grouped by the labels of the panel, and SHALL add no `or vector(0)`, so a panel with no value in the time range shows no data instead of 0.

#### Scenario: The commits of each release
- **WHEN** the panel "Commits per Release" reads the project gauges
- **THEN** its query is `sum by (release) (last_over_time(devops_cli_project_commits[$__range]))`

## ADDED Requirements

### Requirement: An upstream status panel shows the status of the last hour
The panels "GitHub Published Service Status" and "Cloudflare Published Service Status" SHALL read `last_over_time(devops_cli_upstream_service_status{service="<service>"}[1h])` as an instant query, with no `max(`, so each shows the last status sent in the last hour, and no data when none was sent in it.

#### Scenario: An old outage and a new status
- **WHEN** an old series of `github` with the label `indicator="major"` ends, and the series of `github` holds 0 at the time of the read
- **THEN** the panel "GitHub Published Service Status" shows 0

#### Scenario: No status in the last hour
- **WHEN** the last status of `github` was sent more than one hour before the read
- **THEN** the panel "GitHub Published Service Status" shows no data
