# Spec Delta

## ADDED Requirements

### Requirement: The Service shows its budget and each hold
The Service's `/metrics` SHALL hold `devops_cli_service_budget_limit_requests`, the hourly budget, and `devops_cli_service_budget_spent_requests`, the GitHub requests of the last hour as of the last round or check. The Service SHALL add 1 to `devops_cli_service_budget_holds_total` each time a hold begins.

#### Scenario: A hold that begins, ends and begins again
- **WHEN** a budget of 100 sees a round of 130 requests and two checks, then the window slides past that round, then a round of 130 more requests and a check
- **THEN** the gauges and the counter read (limit 100, spent 0, holds 0), then (100, 130, 1), then (100, 0, 1), then (100, 130, 2)

### Requirement: The Service shows each suspended job
`devops_cli_service_job_suspended` SHALL be 1, with the labels `repo` and `row`, while a job has failed its limit of rounds in a row, and 0 after it fails on new input or succeeds. A ledger and a budget read back at start SHALL show what they hold.

#### Scenario: A job that fails its limit of rounds
- **WHEN** a ledger with a limit of 2 counts failures of one job on input a, a, b and b, then a success
- **THEN** the job's gauge reads 0, 1, 0, 1, then 0

#### Scenario: A restart over the same volume
- **WHEN** a new Service starts over a volume whose records hold 60 requests of the window and a suspended job
- **THEN** its budget gauge reads 60 and the job's gauge reads 1
