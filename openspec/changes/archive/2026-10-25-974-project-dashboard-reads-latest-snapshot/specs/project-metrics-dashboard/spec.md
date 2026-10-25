## Purpose

How the Project & Engineering Velocity dashboard (`k8s/monitoring/dashboards/project-metrics.json`) reads the project metrics that the roadmap Service sends as snapshots, and how devops-cli names its gauges and counters so that each consumer reads them by their kind.

## ADDED Requirements

### Requirement: A dashboard reads each series through the function of its kind
Each query of a devops-cli dashboard SHALL read a counter through `rate(` or `increase(`, a gauge through `last_over_time(`, and a histogram through one of these.

#### Scenario: A gauge read with no range
- **WHEN** a panel of a devops-cli dashboard reads a gauge as a plain selector, or through `max(` or `sum(` with no range function
- **THEN** the dashboard invariant of `tests/test_telemetry_instruments.py` fails and names the query and the series

### Requirement: A gauge panel shows the latest value in the time range
Each gauge panel of the project dashboard SHALL read `last_over_time(<metric>[$__range])`, grouped by the labels of the panel, and SHALL add no `or vector(0)`, so a panel with no value in the time range shows no data instead of 0.

#### Scenario: The commits of each release
- **WHEN** the panel "Commits per Release" reads the project gauges
- **THEN** its query is `sum by (release) (last_over_time(devops_cli_project_commits[$__range]))`

### Requirement: Only a counter name ends in `_total`
Each counter that devops-cli sends SHALL have a name that ends in `_total`, and no gauge or histogram SHALL.

#### Scenario: The project gauges
- **WHEN** devops-cli sends the project snapshot
- **THEN** the gauges are `devops_cli_project_releases`, `devops_cli_project_commits`, `devops_cli_project_prs`, `devops_cli_project_ci_runs`, `devops_cli_project_items`, `devops_cli_project_traffic_views`, `devops_cli_project_traffic_views_uniques`, `devops_cli_project_traffic_clones`, `devops_cli_project_traffic_clones_uniques`, `devops_cli_project_traffic_referrers`, `devops_cli_project_traffic_paths`, `devops_cli_project_stars` and `devops_cli_project_forks`
