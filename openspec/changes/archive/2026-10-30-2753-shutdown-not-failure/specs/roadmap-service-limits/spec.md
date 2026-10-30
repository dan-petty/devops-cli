## MODIFIED Requirements

### Requirement: A job that fails each round is suspended
A roadmap job that failed `DEFAULT_SERVICE_MAX_FAILED_ROUNDS` rounds in a row on the same input SHALL NOT run again until its input changes, and a success SHALL clear its count. The log line that suspends a job SHALL name the cause of each of those rounds, and a cause of a round that an earlier process counted SHALL read as `unknown`.

#### Scenario: Polls after the limit
- **WHEN** a job has failed its limit of rounds and only polls follow
- **THEN** the job does not run and the round succeeds

#### Scenario: A webhook after the limit
- **WHEN** a webhook trigger follows
- **THEN** the job runs again

#### Scenario: The cause of the suspension
- **WHEN** a job fails three rounds in a row, with the errors `GitHubOperationError`, `RoadmapRefineError` and `GitHubOperationError`
- **THEN** the log line that suspends the job names those three causes in that order

#### Scenario: A file written by the running version
- **WHEN** the ledger file holds records in the format that the running version writes, and a new process starts over it
- **THEN** the start succeeds and the ledger holds those records, and the file that the new process writes reads with the type that the running version uses

## ADDED Requirements

### Requirement: A round that the stop of the Service ends is not a failed round
A round that ends with the error that the request budget raises when the Service is stopping, or with an error that has it as its cause, SHALL leave the count of failed rounds of its job as it was. A group of errors SHALL be a stop only when each member is. The stage job SHALL end with that error and SHALL make no failed item of it.

#### Scenario: Rounds that a stop ends
- **WHEN** three rounds of a job end with the stop error of the budget, and a normal round follows
- **THEN** the count of the job did not change, the job is not suspended, and the normal round runs the job

#### Scenario: A stop in the cause chain
- **WHEN** a round of a job ends with an error whose cause is the stop error of the budget
- **THEN** the round does not count as a failed round

#### Scenario: A stop does not clear a count
- **WHEN** a job has failed one round for a real reason, a stop ends the next round, and a real failure follows, with the same input each time
- **THEN** the count of the job is 2 after the last round

#### Scenario: A stop in the stage job
- **WHEN** a write of the stage job meets the stop error of the budget
- **THEN** the stage job ends with that error, and it makes no failed item of it

### Requirement: A stop of the Service does not hide a failed item
When an item failed for a real reason before the stop, in the plan or in an earlier write, the stage job and the refine job SHALL end with the failure of those items, so the round counts.

#### Scenario: A stop after a failed item
- **WHEN** an item of the stage job failed for a real reason, in the plan or in an earlier write, and a later write meets the stop error of the budget
- **THEN** the stage job ends with the failure of that item, and the round counts as a failed round

#### Scenario: A stop in the refine job after a failed item
- **WHEN** the model call failed for an item of the refine job, and a write meets the stop error of the budget
- **THEN** the refine job ends with the failure of that item, and the round counts as a failed round
