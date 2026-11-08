## MODIFIED Requirements

### Requirement: A job that fails each round is suspended
A roadmap job that failed `DEFAULT_SERVICE_MAX_FAILED_ROUNDS` rounds in a row on the same input SHALL NOT run again until its input changes or its retry time comes, and a success SHALL clear its count. The ledger SHALL hold, as the cause of each failed round, the failure class of its error (`failure_class_of`); an error that is not an error of the project SHALL have the class `ci_infra`. The log line that suspends a job SHALL name the cause of each of those rounds. The ledger record SHALL hold the causes, so a restart keeps them. A record in the format without causes SHALL load, and its causes SHALL read as `unknown`.

#### Scenario: Polls after the limit
- **WHEN** a job has failed its limit of rounds and only polls follow, before its retry time
- **THEN** the job does not run and the round succeeds

#### Scenario: A webhook after the limit
- **WHEN** a webhook trigger follows
- **THEN** the job runs again

#### Scenario: The cause of the suspension
- **WHEN** a job fails three rounds in a row, with the errors `GitHubOperationError`, `RoadmapRefineError` and `GitHubOperationError`
- **THEN** the log line that suspends the job names the cause `ci_infra` three times

#### Scenario: A plain error
- **WHEN** a job fails with a `ValueError`
- **THEN** the cause of that round is `ci_infra`

#### Scenario: A file written by the running version
- **WHEN** the ledger file holds records in the format that the running version writes, and a new process starts over it
- **THEN** the start succeeds and the ledger holds those records, with their causes

#### Scenario: A restart keeps the causes
- **WHEN** a ledger with the recorded causes `provider` and `plan_defect` is written, and a new process loads the record
- **THEN** the new ledger holds those two causes in that order

#### Scenario: A record from before the causes
- **WHEN** the ledger file holds an entry of a job at the limit, with no causes, and a new process starts over it
- **THEN** the start succeeds, the job is suspended, and its causes read as `unknown`

### Requirement: The Service shows each suspended job
`devops_cli_service_job_suspended` SHALL be 1, with the labels `repo`, `row` and `class`, while a job has failed its limit of rounds in a row, and 0 after it fails on new input or succeeds. The label `class` SHALL be the class of the last cause of the job, or `unknown` when that cause is no failure class. When the class of a job changes, or its entry clears, the series of the old class SHALL read 0. A ledger and a budget read back at start SHALL show what they hold.

#### Scenario: A job that fails its limit of rounds
- **WHEN** a ledger with a limit of 2 counts failures of one job on input a, a, b and b, then a success
- **THEN** the job's gauge reads 0, 1, 0, 1, then 0

#### Scenario: A class that changes
- **WHEN** a job fails twice with the class `provider` and a third time with the class `parser` on one input
- **THEN** the series with `class="parser"` reads 1 and the series with `class="provider"` reads 0

#### Scenario: A restart over the same volume
- **WHEN** a new Service starts over a volume whose records hold 60 requests of the window and a suspended job
- **THEN** its budget gauge reads 60 and the job's gauge reads 1

#### Scenario: A record from before the classes
- **WHEN** the ledger file holds an entry at the limit whose cause is the name `GitHubOperationError`
- **THEN** the gauge of the job reads 1 with `class="unknown"`

### Requirement: The suspension line names the new inputs
The log line that suspends a job SHALL name the failure class of the rounds and the time of the next probe round, and SHALL say that a webhook, a change of an issue or a comment of a person runs the job at once.

#### Scenario: The line names the comment
- **WHEN** a job fails its limit of rounds with the class `provider`
- **THEN** the log line that suspends the job contains `provider`, the time one hour after the last failed round, and `a comment of a person`

## ADDED Requirements

### Requirement: A suspended job runs a probe round after its wait
At or past its limit of failed rounds on one input, a job's ledger entry SHALL get `retry_after`: the time of the round plus `RETRY_AFTER` of the class of the last failure. A job past that time SHALL run one probe round with no new input. A failed probe round SHALL add 1 to the count and set a new `retry_after`. A successful one SHALL clear the entry. A round below the limit SHALL set no `retry_after`.

#### Scenario: The wait of a provider failure
- **WHEN** a job fails its limit of rounds with the class `provider` at 13:30, and polls follow with no new input
- **THEN** the job does not run in the polls before 14:30 and runs in the first poll from 14:30

#### Scenario: The wait of a parser failure
- **WHEN** a job fails its limit of rounds with the class `parser` at 13:30
- **THEN** the job runs in the first poll from 19:30

#### Scenario: A class with no wait
- **WHEN** a job fails its limit of rounds with the class `head_moved`
- **THEN** the job runs in the next round

#### Scenario: A probe round that fails
- **WHEN** the probe round of a job fails on the same input
- **THEN** the count is the limit plus 1 and `retry_after` is the time of that round plus the wait of the class, and the job does not run before it

#### Scenario: A probe round that succeeds
- **WHEN** the probe round of a job succeeds
- **THEN** the ledger holds no entry for the job, and the next failures count from 1

### Requirement: A new input and an old record keep the digest rule
A new input SHALL run a suspended job at once, before its `retry_after`, and a failure on a new input SHALL restart the count at 1 with no `retry_after`. A ledger entry of four or five fields, written before `retry_after`, SHALL load with no `retry_after` and keep the digest rule: the job stays suspended on the same input at any later time. A ledger file that cannot be read SHALL still stop the start with an error that names it.

#### Scenario: A new input before the time
- **WHEN** a webhook round comes before `retry_after`, and the job fails in it
- **THEN** the job ran in that round, its count is 1, and its entry has no `retry_after`

#### Scenario: A lane that reads no change
- **WHEN** a row of the status lane or the model lane is suspended
- **THEN** its input holds the hour of the round, so the row runs in a later hour as before, and `retry_after` ends the suspension of the row `intake` only

#### Scenario: A record of five fields
- **WHEN** the ledger file holds an entry of 5 fields at the limit, and a poll comes 30 days later on the same input
- **THEN** the file loads, the job is suspended, and it runs on a new input

#### Scenario: A record that cannot be read
- **WHEN** the ledger file holds text that is not a record, or an entry whose `retry_after` is no time
- **THEN** the start fails with an error that names the file

### Requirement: The Service shows the seconds before the next probe round
`devops_cli_service_job_retry_after_seconds` SHALL hold, with the labels `repo`, `row` and `class`, the seconds from the last failed round or check of a suspended job to its `retry_after`, and 0 for a job with no `retry_after`, for a job that is past it and for a job that succeeded.

#### Scenario: The seconds fall with the checks
- **WHEN** a job with the class `provider` reaches its limit, and a round checks it 10 minutes later and one hour later
- **THEN** the gauge reads 3600 after the failure, 3000 after the first check and 0 after the second

#### Scenario: A job that succeeds
- **WHEN** a suspended job succeeds in a probe round
- **THEN** the gauge of its last class reads 0
