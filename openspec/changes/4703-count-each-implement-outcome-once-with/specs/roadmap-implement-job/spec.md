## MODIFIED Requirements

### Requirement: Implement job outcome counter
The roadmap Service SHALL increment `devops_cli_service_implement_jobs_total` with the labels `repo`, `item_class` and `result` once for each runner Job that a round reports. The `result` SHALL be `failed` when the report finds a failure class, and the state of the Job (`succeeded`, `failed` or `gone`) otherwise.

#### Scenario: A reported runner Job counts once
- **WHEN** A round reports a runner Job for repository `owner/repo` and item class `feat` that ended Complete with the result `ready`.
- **THEN** The series `devops_cli_service_implement_jobs_total{repo="owner/repo",item_class="feat",result="succeeded"}` increases by one.

#### Scenario: A stop that the runner wrote before it exited 0
- **WHEN** A round of `example/app` reports a runner Job that ended Complete, and its item holds the stop with the class `parser`.
- **THEN** The series with `result` `failed` increases by one, the series with `result` `succeeded` does not change, the failures counter for `parser` and `example/app` increases by one, and a second round adds nothing.

## ADDED Requirements

### Requirement: A round reports the Job of a closed item that the cluster holds
A round SHALL report the Job of a closed item whose record holds `implement.job` and no `implement.job_state` while the cluster lists that Job, and SHALL NOT stop a closed item. A round SHALL NOT report the Job of a closed item that the cluster no longer lists.

#### Scenario: The pull request merged before the report
- **WHEN** the item of a Job closes and the Job then ends Complete
- **THEN** the next round reports the Job once, `implement.job_state` is `succeeded`, `implement.stopped` is not set, and the series with `result` `succeeded` increases by one

#### Scenario: A closed item whose Job is gone
- **WHEN** a closed item records a Job that the cluster does not list
- **THEN** the round records no state and no counter changes

### Requirement: The implement round refuses an empty repository
`run_implement_round` SHALL raise `RoadmapImplementError` before any request to the cluster or to GitHub when `repo` is empty, because each counter of the round carries the label `repo`.

#### Scenario: A round with no repository
- **WHEN** a round runs with an empty `repo`
- **THEN** it raises `RoadmapImplementError` and sends no request to the cluster
