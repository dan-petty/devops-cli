# Spec Delta

## MODIFIED Requirements

### Requirement: The Service submits one implement Job per repository at a time
The status lane of the Service SHALL have a row `implement` after the row `metrics`, due every ten minutes and on a first run, that runs in the job clone of the lane. A round SHALL list the Jobs that carry the label of the repository, and SHALL create no Job while one of them has not ended. Else it SHALL plan the Staged and Planned items that the default filter names, and create one Job from CronJob `devops-cli-runner` for the first of them. The Service SHALL run no step itself.

#### Scenario: A Staged low-effort P1 bug
- **WHEN** the Kubernetes API is faked with CronJob `devops-cli-runner`, and a round of the row runs on a Staged Ready P1 bug of low effort
- **THEN** the API receives one Job create, and a second round with the Job still running creates no second Job

#### Scenario: A running Job of another item
- **WHEN** a Job of the repository has no Complete or Failed condition, and a second Staged item is ready
- **THEN** the round creates no Job

#### Scenario: The template is missing
- **WHEN** CronJob `devops-cli-runner` does not exist
- **THEN** the round raises an error that names the CronJob and the namespace, and creates no Job

#### Scenario: A Planned item
- **WHEN** the plan of a Ready P1 bug of low effort is on `origin/main` and its branch is gone
- **THEN** the round creates one Job with the args of that item

## ADDED Requirements

### Requirement: A model-lane round that has not ended does not delay the implement row
The row `implement` SHALL NOT be a row of the model lane. A poll SHALL make it due on the status lane by its interval, whether or not a round of the model lane of the same repository is running. A suspended `implement` row in the ledger of failed rounds SHALL stay suspended on the status lane until the hour ends, and a ledger record that holds an entry of the row SHALL load.

#### Scenario: The model lane is in a long refine round
- **WHEN** the model lane runs a refine round that has not ended, and a poll reaches both lanes of the repository
- **THEN** the status lane runs `metrics` and `implement` while the refine round is still running

#### Scenario: The rows of each lane
- **WHEN** the due table is read
- **THEN** the status lane holds `metrics` and then `implement`, and the model lane holds `intake`, `refine`, `stage` and `alternatives`

#### Scenario: A suspended row keeps its suspension
- **WHEN** the record of failed rounds holds an entry of the row `implement` at the limit of rounds, and the status lane runs a round on the same input
- **THEN** the record loads, the row does not run, and the gauge `devops_cli_service_job_suspended` for the row is 1

#### Scenario: A suspended row runs again in a later hour
- **WHEN** the row `implement` failed its limit of rounds in a row, its fault is fixed, and a poll round of a later hour runs on the status lane
- **THEN** the row runs, with no webhook
