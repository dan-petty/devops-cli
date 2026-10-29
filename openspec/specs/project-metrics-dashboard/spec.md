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

### Requirement: A label set that has no items is sent as 0 once
After a snapshot, `emit_project_metrics_telemetry` SHALL send the value 0 for each label set that the last snapshot of the same process sent and the new snapshot does not hold. It SHALL send that 0 once.

#### Scenario: The last item of a label set closes
- **WHEN** a snapshot holds one open item of type `bug`, and the next snapshot holds that item as closed
- **THEN** the next snapshot sends 0 for the open set and 1 for the closed set, and the snapshot after it sends neither the 0 nor the open set

### Requirement: A gauge reaches Prometheus through one path
Each gauge that devops-cli sends SHALL reach Prometheus through one path: through OTLP export, or through a Prometheus scrape endpoint, and never through both. No gauge sent over OTLP SHALL be registered or recorded in an in-memory Prometheus metrics registry or exposed by a Prometheus scrape endpoint.

#### Scenario: Two paths send the same gauge name
- **WHEN** an instrument sent over OTLP as a gauge has the same name as a gauge recorded in an in-memory Prometheus registry or exposed by a Prometheus scrape endpoint
- **THEN** the telemetry invariant check fails and names the shared gauge names

### Requirement: The panels that read the items gauge group them by release
The panels "Items by Release" and "Active Items by State" SHALL group `devops_cli_project_items` only by labels that the gauge sends. The description of each panel and of the instrument SHALL name the labels, and the panel "Items by Release" SHALL show an item in no release as `unreleased`.

#### Scenario: A panel groups by a label that the gauge does not send
- **WHEN** a query of the project dashboard groups `devops_cli_project_items` by a label that is not `release`, `state`, `type` or `priority`
- **THEN** the dashboard invariant of `tests/test_telemetry_instruments.py` fails and names the query and the label

#### Scenario: The items of each release
- **WHEN** the panel "Items by Release" reads the items gauge
- **THEN** its query is `label_replace(sum by (release, state) (last_over_time(devops_cli_project_items[$__range])), "release", "unreleased", "release", "^$")`

#### Scenario: The items of each state
- **WHEN** the panel "Active Items by State" reads the items gauge
- **THEN** its query is `sum by (state) (last_over_time(devops_cli_project_items[$__range]))`

### Requirement: The items gauge counts the Items of the repository by release
`devops_cli_project_items` SHALL count the Items of the repository, open and closed, with the labels `release`, `state`, `type` and `priority`. The `release` label SHALL be the first `v*` tag whose commits close the Item with a closing keyword, and empty for an open Item or a closed Item that no release holds. The `type` label SHALL be the `type/*` label of the issue without its prefix, empty when the issue has none, and the `priority` label SHALL be the Item's Priority.

#### Scenario: An open Item
- **WHEN** the repository holds two open issues with `type/bug` and `priority/p1-high`
- **THEN** the report has one item count with `release` empty, `state` `open`, `type` `bug`, `priority` `P1-High` and a count of 2

#### Scenario: A closed Item that a release closed
- **WHEN** a commit in the range of the tag `v0.2.24` has the footer `Closes #2`, and issue 2 is a closed Item
- **THEN** the report counts issue 2 with `release` `v0.2.24` and `state` `closed`

#### Scenario: An issue closed again in a later release
- **WHEN** a commit of `v0.1.0` has `Closes #4`, and a commit of `v0.2.0` has `fixes #4`
- **THEN** the release of issue 4 is `v0.1.0`

#### Scenario: A pull request or an issue that is not an Item
- **WHEN** the repository has a pull request with `priority/p1-high`, and an issue with no `priority/*` label
- **THEN** the report counts neither

#### Scenario: The issues cannot be read
- **WHEN** the read of the issues fails
- **THEN** the collection of the report raises the failure and returns no report
