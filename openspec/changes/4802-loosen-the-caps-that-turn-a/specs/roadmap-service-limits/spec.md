## MODIFIED Requirements

### Requirement: A job that fails each round is suspended
A roadmap job that failed `service.max_failed_rounds` rounds (default 6) in a row on the same input SHALL NOT run again until its input changes or its retry time comes, and a success SHALL clear its count. The ledger SHALL hold, as the cause of each failed round, the failure class of its error (`failure_class_of`); an error that is not an error of the project SHALL have the class `ci_infra`. The log line that suspends a job SHALL name the cause of each of those rounds.

#### Scenario: Polls after the limit
- **WHEN** a job has failed its limit of rounds and only polls follow, before its retry time
- **THEN** the job does not run and the round succeeds

#### Scenario: A webhook after the limit
- **WHEN** a webhook trigger follows
- **THEN** the job runs again

#### Scenario: The cause of the suspension
- **WHEN** a job with a limit of three rounds fails three rounds in a row, with the errors `GitHubOperationError`, `RoadmapRefineError` and `GitHubOperationError`
- **THEN** the log line that suspends the job names the cause `ci_infra` three times

#### Scenario: The limit follows the setting
- **WHEN** `service.max_failed_rounds` is 4 and a job fails three rounds in a row on the same input
- **THEN** the job is not suspended, and a fourth failed round suspends it

#### Scenario: A plain error
- **WHEN** a job fails with a `ValueError`
- **THEN** the cause of that round is `ci_infra`
