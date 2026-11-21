## MODIFIED Requirements

### Requirement: A Service metric query names its repository
The catalog schema SHALL refuse a `prometheus` fact whose query names a metric that starts with `devops_cli_service_` and holds no `{repo}` placeholder. The loader SHALL also refuse each selector of such a metric, in the query or in the `base` metric of a fact, whose own braces hold no matcher `repo="{repo}"`.

#### Scenario: A Service metric with no repository is refused
- **WHEN** the query of the `prometheus` fact `prometheus.stage_runs` is `sum(increase(devops_cli_service_jobs_total{row="stage"}[{range}]))`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.stage_runs`

#### Scenario: A ratio whose numerator has no repository is refused
- **WHEN** the query of the fact `prometheus.service_slo1` is `sum(increase(devops_cli_service_jobs_total{row="stage", result="success"}[{range}])) / sum(increase(devops_cli_service_jobs_total{repo="{repo}", row="stage"}[{range}]))`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.service_slo1` and `devops_cli_service_jobs_total`

### Requirement: A Service SLI is the value of one repository
A fact on a Service metric SHALL give the value of the repository of the review, and SHALL NOT add the values of the repositories together.

#### Scenario: Seven repositories
- **WHEN** a fixture Prometheus gives the SLO 1 of the Service 0.372 for `example/project` and 0.555 for each of six other repositories, and gives 0.927 for a query with no `repo` matcher
- **THEN** the fact `prometheus.service_slo1` of `example/project` has the value 0.372

### Requirement: An empty answer is none only when its base metric has a series
A `prometheus` fact can name a `base` metric. When its query matches no series and the base metric has a series, the fact SHALL have the status `ok` with no rows, or 0 for a `scalar` fact; else `skipped` with a reason that names the base metric. The probe SHALL have the time scope of the query: `group(last_over_time(<base>[<range>]))` when the query holds `{range}`, else `group(<base>)` at the window end.

#### Scenario: An empty answer of a fact with a base metric
- **WHEN** a fixture Prometheus answers the query `sum by (row) (increase(x_total[{range}])) > 0` of a fact with the base metric `x_total{repo="{repo}"}` with an empty vector, and answers `group(last_over_time(x_total{repo="example/project"}[604800s]))` with one series
- **THEN** a `rows` fact has the status `ok`, the value `[]` and `n` 0, and a `scalar` fact has the status `ok` and the value 0

#### Scenario: An empty answer and no base series
- **WHEN** the fixture Prometheus also answers the read of the base metric with an empty vector
- **THEN** the fact has the status `skipped`, a null value and a reason that names the base metric

#### Scenario: An end-instant fact whose base has no series at the end
- **WHEN** a fact with the base `x_total{repo="{repo}"}` has the query `sum by (state) (x_total)` with no `{range}`, and the fixture Prometheus answers it with an empty vector, answers `group(last_over_time(x_total{repo="example/project"}[604800s]))` with one series, and answers `group(x_total{repo="example/project"})` with an empty vector
- **THEN** the fact has the status `skipped`, a null value and a reason that names the base metric and the window end, and the sent queries are the query and `group(x_total{repo="example/project"})`

## ADDED Requirements

### Requirement: The base metric of a fact is a metric of its query
The loader SHALL refuse a fact whose `base` metric name does not occur as a whole metric name in its query, unless the fact gives `base_reason`, a text that says why its base is another metric. The refusal SHALL raise `RoadmapReviewError` with a message that names the fact, the base metric and `base_reason`. The schema SHALL refuse `base_reason` in a fact with no `base`.

#### Scenario: A base of another metric is refused
- **WHEN** a fixture catalog holds the fact `prometheus.cuts` with the query `sum(increase(x_cuts_total[{range}]))` and the base `x_calls_total`
- **THEN** the loader raises `RoadmapReviewError`, and the message names `prometheus.cuts`, `x_calls_total` and `base_reason`

#### Scenario: A base of another metric with a reason loads
- **WHEN** the same fact also gives `base_reason` with a text
- **THEN** the loader gives the catalog with that fact

#### Scenario: A metric name inside a longer name does not count
- **WHEN** the query of the fact is `sum(increase(x_calls_total_bucket[{range}]))` and the base is `x_calls_total`
- **THEN** the loader raises `RoadmapReviewError`

#### Scenario: A reason with no base is refused
- **WHEN** a fixture fact gives `base_reason` and no `base`
- **THEN** the loader raises `RoadmapReviewError`, and the message names the fact and `base_reason`

#### Scenario: The shipped catalog loads
- **WHEN** the loader reads the shipped `catalog.yaml`
- **THEN** it raises no error

### Requirement: A fact can name the first time of its series
A fact MAY give `not_before`, a UTC time `YYYY-MM-DDTHH:MM:SSZ`. When the window starts before it, the dispatcher SHALL give the fact the status `skipped` with a reason that names that time, and SHALL send no request for it. The dry run SHALL show the condition.

#### Scenario: A window across the first time of a series
- **WHEN** a fixture catalog holds `prometheus.left` and `prometheus.right` with `not_before` `2026-11-14T22:29:00Z` and the pair of both with the tolerance 0.1, the window is the 7 days to `2026-11-16T00:00:00Z`, and the fixture Prometheus answers 48.43 for each query
- **THEN** `prometheus.left` is `ok` with 48.43, `prometheus.right` is `skipped` with a reason that names `2026-11-14T22:29:00Z`, the query of `prometheus.right` is not sent, and the review lists no disagreement

#### Scenario: A window after the first time of a series
- **WHEN** the window is the 1 day to `2026-11-16T00:00:00Z`, and the fixture Prometheus answers 48.43 for the left query and 15 for the right query
- **THEN** both facts are `ok`, and the review lists the disagreement of the pair

#### Scenario: The dry run shows the first time
- **WHEN** the plan of a dry run holds the fixture fact `prometheus.right`
- **THEN** the condition of its read says that the window starts at or after `2026-11-14T22:29:00Z`

#### Scenario: A time that is not UTC is refused
- **WHEN** a fixture fact gives `not_before` `2026-11-14T22:29:00+01:00`
- **THEN** the loader raises `RoadmapReviewError`, and the message names the fact and `not_before`

### Requirement: The runner Job count reads the Jobs that start in the window
The shipped fact `prometheus.runner_jobs_started` SHALL count the implement Jobs of the repository of the review whose start time is at or after the window start. It SHALL NOT count a Job that started before the window, also when kube-state-metrics keeps the series of that Job in the window.

#### Scenario: A Job that started before the window and a Job that started in it
- **WHEN** promtool evaluates the query of the shipped `prometheus.runner_jobs_started`, filled for `example/project` and the window from `1970-01-01T01:00:00Z` to `1970-01-01T02:00:00Z`, over fixture series of `kube_job_status_start_time` of an implement Job of `example/project` that started before the window and has a series in it, an implement Job of `example/project` that started in the window, and an implement Job of another repository that started in the window
- **THEN** the value is 1

#### Scenario: Only a Job that started before the window
- **WHEN** the fixture series hold only the implement Job of `example/project` that started before the window
- **THEN** the query gives no series

### Requirement: A path condition holds at the commits of the window
A `path:<path>` condition SHALL hold when the base and the head commits of the window hold the path, as `git ls-tree --name-only <commit> -- <path>` gives it, not the working tree. Else the fact SHALL be `skipped` with a reason that names the path and the commit. The dispatcher SHALL check each path once for each review. A git failure SHALL stop the review. The dry run SHALL list the two git commands.

#### Scenario: A base commit with no specs
- **WHEN** the window of a fixture repository has a base commit with no `openspec/specs` and a head commit with it, and the working tree holds `openspec/specs`
- **THEN** each `openspec` fact has the status `skipped`, a null value and a reason that names `openspec/specs` and the base commit, and the review starts no other git command for it

#### Scenario: The dry run lists the path checks
- **WHEN** a person runs `devops roadmap review run --last 7d --dry-run`
- **THEN** the output lists the git command `ls-tree --name-only` of `<base commit>` and of `<head commit>`, each with the path `openspec/specs`, and no program starts

### Requirement: A fact can give the reason of a missing series
A fact with no `base` MAY give `no_series_reason`, a text. When its query matches no series, the fact SHALL have the status `skipped` and that text as its reason. The schema SHALL refuse `no_series_reason` in a fact with a `base`.

#### Scenario: A gauge that no code emits yet
- **WHEN** a fixture fact with no `base` gives the `no_series_reason` "No code emits this gauge before #4911." and the fixture Prometheus answers its query with an empty vector
- **THEN** the fact has the status `skipped`, a null value and the reason "No code emits this gauge before #4911."

#### Scenario: A reason of a missing series with a base is refused
- **WHEN** a fixture fact gives `no_series_reason` and `base`
- **THEN** the loader raises `RoadmapReviewError`, and the message names the fact

### Requirement: The stage SLI counts the outcomes of the stage items
The shipped fact `prometheus.stage_sli` SHALL be the share of the stage items of the repository of the review that ended `staged` or `needs_split`, over the items of `devops_cli_roadmap_stage_total` that ended with a result other than `skipped`. It SHALL be 0 when no item ended well, and have no value when no item ended. Its definition SHALL name the owner decision of 2026-11-21 on #4692.

#### Scenario: Good and bad outcomes of one repository
- **WHEN** promtool evaluates the query of the shipped `prometheus.stage_sli`, filled for `example/project` and a window of 1 hour, over fixture series that add 6 `staged`, 2 `needs_split`, 1 `failed`, 1 `degenerate` and 5 `skipped` items of `example/project` and 10 `failed` items of `example/other` in the window
- **THEN** the value is 0.8

#### Scenario: Only bad outcomes
- **WHEN** the fixture series add only 3 `failed` items of `example/project`
- **THEN** the value is 0

#### Scenario: Only skipped items
- **WHEN** the fixture series add only 5 `skipped` items of `example/project`
- **THEN** the query gives no series
