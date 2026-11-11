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
After a snapshot of a repository, `emit_project_metrics_telemetry` SHALL send the value 0, with the `repo` of that repository, for each label set that the last snapshot of the same repository in the same process sent and the new snapshot does not hold. It SHALL send that 0 once, and SHALL send no 0 for a label set of another repository.

#### Scenario: The last item of a label set closes
- **WHEN** a snapshot holds one open item of type `bug`, and the next snapshot of the same repository holds that item as closed
- **THEN** the next snapshot sends 0 for the open set and 1 for the closed set, and the snapshot after it sends neither the 0 nor the open set

#### Scenario: A snapshot of a second repository
- **WHEN** a snapshot of `Example/One` holds one open item of type `bug`, and the next snapshot in the process is of `Example/Two` with one closed item of type `feature`
- **THEN** the snapshot of `Example/Two` sends only its closed set with `repo=example/two`, and no point with the value 0

#### Scenario: A label set leaves one of two repositories
- **WHEN** snapshots of `Example/One` and `Example/Two` each hold one open item of type `bug`, and the next snapshot of `Example/One` holds that item as closed
- **THEN** that snapshot sends 0 for the open set and 1 for the closed set, both with `repo=example/one`, and sends no point with `repo=example/two`

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

### Requirement: The Service collects no repository traffic
A process that acts as the GitHub App SHALL send no request to the four repository traffic endpoints (`traffic/views`, `traffic/clones`, `traffic/popular/referrers` and `traffic/popular/paths`) when it collects the project metrics, and the report SHALL have `traffic_collected` false. A process that acts as a person SHALL send the four requests, and the report SHALL have `traffic_collected` true.

#### Scenario: A run from a workstation
- **WHEN** `get_repository_traffic_metrics` runs in a process that does not act as the App
- **THEN** it sends one request to each of the four traffic paths and the report has `traffic_collected` true

#### Scenario: A collection under the App
- **WHEN** `get_repository_traffic_metrics` runs in a process that acts as the GitHub App, and GitHub is faked at the `gh` edge
- **THEN** no request goes to a path that starts with `repos/<repo>/traffic/` and the report has `traffic_collected` false

#### Scenario: The command prints the report of the App
- **WHEN** `devops gh metrics` prints a report whose `traffic_collected` is false
- **THEN** its traffic line says "not collected" and shows no count of views or clones

### Requirement: A report without traffic sends no traffic gauge
`emit_project_metrics_telemetry` SHALL send none of the six `devops_cli_project_traffic_*` gauges for a report whose `traffic_collected` is false, and SHALL still send the stars and the forks.

#### Scenario: A round of the metrics row under the App
- **WHEN** the metrics row runs in a process that acts as the GitHub App, and GitHub is faked at the `gh` edge
- **THEN** the row sends no `devops_cli_project_traffic_*` point and sends `devops_cli_project_stars` and `devops_cli_project_forks`

### Requirement: A path that the token cannot read is not asked again
The project metrics collector SHALL NOT send a GitHub path again in the same process after GitHub answered that path with HTTP 403 and the message "Resource not accessible by integration". Another repository, another endpoint and any other failure SHALL NOT set the guard. A new process SHALL start with no refused path.

#### Scenario: Two collections after a refusal
- **WHEN** GitHub answers `repos/example/repo/traffic/views` with 403 "Resource not accessible by integration", and the collector reads the traffic of `example/repo` twice
- **THEN** the path is requested once, and the other three traffic paths are requested twice

#### Scenario: Another repository
- **WHEN** the path of `example/one` was refused and the collector reads the traffic of `example/two`
- **THEN** the path `repos/example/two/traffic/views` is requested

#### Scenario: A failure that is not a refusal by the token
- **WHEN** GitHub answers a traffic path with a 502 or with a 403 of another message, such as "Must have push access", and the collector reads the traffic again
- **THEN** the path is requested again

### Requirement: The metrics row sends the age of the oldest item in each state
In each round, the metrics row SHALL send, for its repository, two gauges for each pair of a Status value and a `plan` flag. The gauges are `devops_cli_roadmap_item_age_seconds` and `devops_cli_roadmap_oldest_item_number`, with the labels `repo`, `state` and `plan`. The age is the clock minus the time of the `labeled` event of the oldest open Item of the pair. A pair with no Item sends 0 for both gauges.

#### Scenario: The age comes from the label event and the clock
- **WHEN** an open Item got the label `status/ready` at time T, and the clock reads T plus 3600 seconds
- **THEN** the point with `state` `ready` has the age 3600 and the number of that Item

#### Scenario: The oldest Item of a pair
- **WHEN** two open Items got `status/ready` at T and at T plus 600 seconds, and the clock reads T plus 3600 seconds
- **THEN** the age of the pair is 3600 and its number is the number of the first Item

#### Scenario: A label that a person removed and added again
- **WHEN** an Item got `status/ready` at T, lost it at T plus 100 seconds, and got it again at T plus 200 seconds
- **THEN** the age counts from T plus 200 seconds

#### Scenario: The plan flag
- **WHEN** the job record of a Ready Item holds `stage.pr`, and the job record of another Ready Item holds none
- **THEN** the first sends `plan` `true` and the second sends `plan` `false`

#### Scenario: A pair with no Item
- **WHEN** no open Item is Blocked
- **THEN** the round sends the age 0 and the number 0 for `state` `blocked`, for both values of `plan`

### Requirement: The metrics row sends the age of the oldest claim
`devops_cli_roadmap_claim_age_seconds` SHALL carry the label `repo`. Its value SHALL be the clock minus the time of the `labeled` event of the current `owner/*` label. The labeled Item is the open Item whose claim is oldest. The value SHALL be 0 when no open Item holds a claim.

#### Scenario: Two claims
- **WHEN** an Item got `owner/agent` at T and another got `owner/service` at T plus 600 seconds, and the clock reads T plus 3600 seconds
- **THEN** the claim age is 3600

### Requirement: The label events of an Item are read when its labels change
The metrics row SHALL read the label changes of an open Item that holds a Status or an Owner label. It SHALL do so in the first round of the process that sees its current Status and Owner labels. It SHALL NOT read them again while those labels stay the same.

#### Scenario: Two rounds with no change
- **WHEN** two rounds run over the same Items and labels
- **THEN** the second round sends no request to the events of an issue

#### Scenario: A Status that changed
- **WHEN** a person changes the Status label of one Item between two rounds
- **THEN** the second round reads the events of that issue only, and the age counts from the new event

### Requirement: A failed read of the label events keeps the other metrics
When the read of the label changes of an Item fails, `collect_project_metrics_report` SHALL log a warning. It SHALL return the other sections of the report whole, and no age. The row SHALL send no age point in that round.

#### Scenario: GitHub answers HTTP 500 for an events listing
- **WHEN** GitHub answers HTTP 500 for `issues/<number>/events`
- **THEN** the round sends the item counts and the releases, no age point, and the log holds a warning that names the repository

### Requirement: A run from a person's login sends no age
`devops gh metrics --emit-telemetry` SHALL send none of the three roadmap age gauges, and SHALL send no request to the events of an issue.

#### Scenario: The command emits the report
- **WHEN** `devops gh metrics --emit-telemetry` runs and GitHub is faked at the `gh` edge
- **THEN** no age point is sent and no request path ends in `/events`

### Requirement: The dashboard shows the age of the oldest item in each state
The project dashboard SHALL hold the timeseries panel "Oldest Item Age by State" in the row of the items panels, with the unit `s`. Its queries SHALL be `max by (state) (last_over_time(devops_cli_roadmap_item_age_seconds[$__range]))` and `max(last_over_time(devops_cli_roadmap_claim_age_seconds[$__range]))`. It SHALL leave the right half of its row free.

#### Scenario: The queries of the panel
- **WHEN** a test reads the panel "Oldest Item Age by State" of `project-metrics.json`
- **THEN** its two queries are the ones above, each names a declared instrument, and no panel overlaps it

### Requirement: Each project series carries the repository of its snapshot
Each point of a `devops_cli_project_*` instrument SHALL carry the label `repo`, the casefolded `owner/name` of the report that holds the value, so the snapshots of two repositories never share a series. The description of each such instrument SHALL name `repo`.

#### Scenario: Two repositories in one process
- **WHEN** a test emits the report of `Example/One` with 2 stars and then the report of `Example/Two` with 7 stars, in one process
- **THEN** each `devops_cli_project_*` instrument has points with `repo=example/one` and points with `repo=example/two`, and the stars points are 2 for `example/one` and 7 for `example/two`

#### Scenario: A reader of the instruments
- **WHEN** a test reads the description of each `devops_cli_project_*` instrument of `INSTRUMENTS`
- **THEN** each description names `repo`, and the description of `devops_cli_project_items` also names `release`, `state`, `type` and `priority`

### Requirement: A snapshot for telemetry holds the whole repository
`devops gh metrics --emit-telemetry` SHALL exit with an error that names the refused option when `--milestone` is given or `--limit` is not its default of 10. It SHALL refuse before any request and send no point. With no `--limit` or with `--limit 10`, it SHALL send the snapshot.

#### Scenario: A filtered snapshot
- **WHEN** a test runs `devops gh metrics --emit-telemetry --milestone 2026-11` and `devops gh metrics --emit-telemetry --limit 5`
- **THEN** each run exits non-zero, its output names the refused option, no `gh` or `git` program runs, and no `devops_cli_project_*` point is sent

#### Scenario: The default limit
- **WHEN** a test runs `devops gh metrics --repo example/repo --emit-telemetry` with no `--limit`, and with `--limit 10`
- **THEN** each run exits 0 and sends the stars point with `repo=example/repo`
