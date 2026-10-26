# project-metrics-dashboard Specification

## Purpose
How the Project & Engineering Velocity dashboard (`k8s/monitoring/dashboards/project-metrics.json`) reads the project metrics that the roadmap Service sends as snapshots, and how devops-cli names its gauges and counters so that each consumer reads them by their kind.

## Requirements

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

### Requirement: The items gauge counts the items of the project board
`devops_cli_project_items` SHALL count the items of the project board, open and closed, with the labels `milestone`, `state`, `type` and `priority`. The `milestone` label SHALL be empty for an item in no milestone. The `type` label SHALL be the `type/*` label of the issue without its prefix, and the `priority` label SHALL be the board Priority, each empty when the item has none.

#### Scenario: An open item in no milestone
- **WHEN** the board holds two open items of type `bug` with Priority `P1-High` and no milestone
- **THEN** the report has one item count with `milestone` empty, `state` `open`, `type` `bug`, `priority` `P1-High` and a count of 2

#### Scenario: Open and closed items of a milestone
- **WHEN** the board holds one open item and one closed item in the milestone `2026-11-01`
- **THEN** the report has one count for each state, and both name the milestone `2026-11-01`

#### Scenario: A pull request or an issue that is not on the board
- **WHEN** the repository has a pull request, and an issue with no card on the board
- **THEN** the report counts neither

#### Scenario: The board cannot be read
- **WHEN** the read of the board fails
- **THEN** the collection of the report raises the failure and returns no report

### Requirement: A label set that has no items is sent as 0 once
After a snapshot, `emit_project_metrics_telemetry` SHALL send the value 0 for each label set that the last snapshot of the same process sent and the new snapshot does not hold. It SHALL send that 0 once.

#### Scenario: The last item of a label set closes
- **WHEN** a snapshot holds one open item of type `bug`, and the next snapshot holds that item as closed
- **THEN** the next snapshot sends 0 for the open set and 1 for the closed set, and the snapshot after it sends neither the 0 nor the open set

### Requirement: The panels that read the items gauge describe what it counts
The panels "Items by Milestone" and "Active Items by State" SHALL group `devops_cli_project_items` only by labels that the gauge sends. The description of each panel and of the instrument SHALL name the labels, and the panel "Items by Milestone" SHALL show an item in no milestone as `none`.

#### Scenario: A panel groups by a label that the gauge does not send
- **WHEN** a query of the project dashboard groups `devops_cli_project_items` by a label that is not `milestone`, `state`, `type` or `priority`
- **THEN** the dashboard invariant of `tests/test_telemetry_instruments.py` fails and names the query and the label

#### Scenario: The items of each milestone
- **WHEN** the panel "Items by Milestone" reads the items gauge
- **THEN** its query is `label_replace(sum by (milestone, state) (last_over_time(devops_cli_project_items[$__range])), "milestone", "none", "milestone", "^$")`

#### Scenario: The items of each state
- **WHEN** the panel "Active Items by State" reads the items gauge
- **THEN** its query is `sum by (state) (last_over_time(devops_cli_project_items[$__range]))`

### Requirement: A gauge reaches Prometheus through one path
Each gauge that devops-cli sends SHALL reach Prometheus through one path: through OTLP export, or through a Prometheus scrape endpoint, and never through both. No gauge sent over OTLP SHALL be registered or recorded in an in-memory Prometheus metrics registry or exposed by a Prometheus scrape endpoint.

#### Scenario: Two paths send the same gauge name
- **WHEN** an instrument sent over OTLP as a gauge has the same name as a gauge recorded in an in-memory Prometheus registry or exposed by a Prometheus scrape endpoint
- **THEN** the telemetry invariant check fails and names the shared gauge names
