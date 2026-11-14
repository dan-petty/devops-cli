## ADDED Requirements

### Requirement: The parallel limit is a setting
The Service SHALL read the setting `roadmap.implement.max_parallel_jobs` as a whole number of at least 1, and SHALL use 1 when the configuration holds no value. The setting SHALL have the default 1 and the variable `DEVOPS_CLI_ROADMAP_IMPLEMENT_MAX_PARALLEL_JOBS`.

#### Scenario: Default limit
- **WHEN** the configuration holds no value for the parallel limit setting
- **THEN** the implement round reports a limit of 1 and creates at most one implement Job

#### Scenario: A limit of two
- **WHEN** the setting is 2 and two eligible items of one repository have disjoint change file sets
- **THEN** the round creates two implement Jobs

### Requirement: An item with a claim or a labelled Job gets no second Job
The Service SHALL create no second Job for an item that has a claim or a running Job that carries the item label of that item.

#### Scenario: Claimed item
- **WHEN** an eligible item has a claim or a running Job with its item label
- **THEN** the round creates no Job for that item and creates the Jobs of the other selected items

## MODIFIED Requirements

### Requirement: The Service submits implement Jobs for the disjoint items of one repository
The status lane of the Service SHALL have a row `implement` after `metrics`, due every ten minutes, in the lane's job clone. A round SHALL count the Jobs with the repository label that have not ended, against the setting `roadmap.implement.max_parallel_jobs`. It SHALL plan the Staged and Planned items of the default filter up to the free slots, and create one Job for each from CronJob `devops-cli-runner`, in plan order. The Service SHALL run no step itself.

#### Scenario: A Staged low-effort P1 bug
- **WHEN** the Kubernetes API is faked with CronJob `devops-cli-runner`, and a round of the row runs on a Staged Ready P1 bug of low effort
- **THEN** the API receives one Job create, and a second round with the Job still running creates no second Job

#### Scenario: A running Job of another item
- **WHEN** a Job of the repository has no Complete or Failed condition and carries the item label of one item, a second Staged item is ready with a disjoint change set, and the setting is 2
- **THEN** the round creates one Job, for the second item

#### Scenario: The template is missing
- **WHEN** CronJob `devops-cli-runner` does not exist
- **THEN** the round raises an error that names the CronJob and the namespace, and creates no Job

#### Scenario: A Planned item
- **WHEN** the plan of a Ready P1 bug of low effort is on `origin/main` and its branch is gone
- **THEN** the round creates one Job with the args of that item

## RENAMED Requirements

- FROM: `### Requirement: The Service submits one implement Job per repository at a time`
- TO: `### Requirement: The Service submits implement Jobs for the disjoint items of one repository`
