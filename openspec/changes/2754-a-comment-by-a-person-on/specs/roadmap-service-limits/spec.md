## MODIFIED Requirements

### Requirement: A job that fails each round is suspended
A roadmap job that failed `DEFAULT_SERVICE_MAX_FAILED_ROUNDS` rounds in a row on the same input SHALL NOT run again until its input changes, and a success SHALL clear its count. The input of a round SHALL hold the newest comment that a person made on an Item of the row after the row's last success, and SHALL hold no comment that the Service's own account made. The log line that suspends a job SHALL name the cause of each of those rounds, and a cause of a round that an earlier process counted SHALL read as `unknown`.

#### Scenario: Polls after the limit
- **WHEN** a job has failed its limit of rounds and only polls follow
- **THEN** the job does not run and the round succeeds

#### Scenario: A webhook after the limit
- **WHEN** a webhook trigger follows
- **THEN** the job runs again

#### Scenario: A person's comment after the limit
- **WHEN** a job has failed its limit of rounds and a person comments on one of its Items
- **THEN** the job's input differs from the input it failed on, and the job runs again

#### Scenario: The Service's own comment after the limit
- **WHEN** a job has failed its limit of rounds and the Service's account comments on one of its Items
- **THEN** the job's input is the one it failed on, and the job does not run

#### Scenario: The cause of the suspension
- **WHEN** a job fails three rounds in a row, with the errors `GitHubOperationError`, `RoadmapRefineError` and `GitHubOperationError`
- **THEN** the log line that suspends the job names those three causes in that order

#### Scenario: A file written by the running version
- **WHEN** the ledger file holds records in the format that the running version writes, and a new process starts over it
- **THEN** the start succeeds and the ledger holds those records, and the file that the new process writes reads with the type that the running version uses
