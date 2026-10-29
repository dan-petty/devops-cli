# roadmap-service-limits Specification

## Purpose
Defines when the roadmap Service stops, holds or skips its GitHub work, so a refused identity, a spent hourly budget or a job that fails at each round never makes the Service send requests without bound.

## Requirements

### Requirement: A refused identity stops the Service
When a round fails because GitHub refused the Service's identity, the Service SHALL start no round for any repository or lane, also after a restart, until a person removes its halt record and restarts it, SHALL send no later job of the failed round, and SHALL report the refusal once with one error log line and one count of `devops_cli_service_identity_refused_total` that name the identity.

#### Scenario: A suspended account
- **WHEN** a job fails with `gh: Sorry. Your account was suspended. (HTTP 403)` and triggers keep arriving for every repository
- **THEN** no other job starts, and exactly one error line and one metric count name the account

#### Scenario: Another failure
- **WHEN** a round fails for a reason that is not a refused identity
- **THEN** the Service starts later rounds as usual

### Requirement: Requests stay under an hourly budget
The Service SHALL start no round while the GitHub requests of the last hour reach `service.github_requests_per_hour`, SHALL run the held triggers as one round for each lane of each repository when the window has room, and SHALL poll no faster than the budget pays for at the measured cost of a round.

#### Scenario: A spent budget
- **WHEN** the rounds of the last hour sent as many requests as the budget
- **THEN** a trigger that arrives starts no round until an hour has passed since those requests

#### Scenario: A costly round
- **WHEN** the rounds of one poll cost more than the budget pays for at the configured interval
- **THEN** the next poll comes after the longer interval that the budget gives

### Requirement: A job that fails each round is suspended
A roadmap job that failed `DEFAULT_SERVICE_MAX_FAILED_ROUNDS` rounds in a row on the same input SHALL NOT run again until its input changes, and a success SHALL clear its count.

#### Scenario: Polls after the limit
- **WHEN** a job has failed its limit of rounds and only polls follow
- **THEN** the job does not run and the round succeeds

#### Scenario: A webhook after the limit
- **WHEN** a webhook trigger follows
- **THEN** the job runs again

### Requirement: A suspended installation and a header-less 403 to a write are refusals
The Service SHALL read as a refused identity a reply that says the App installation is suspended, and a 403 to a write whose answer has no `x-ratelimit-*` header.

#### Scenario: A suspended installation
- **WHEN** a job's write through gh fails with `gh: This installation has been suspended (HTTP 403)`
- **THEN** the Service halts, and one metric count names the identity

#### Scenario: A write refused with no rate-limit header
- **WHEN** a job's write through the GitHub session gets a 403 whose answer has no `x-ratelimit-*` header
- **THEN** the Service halts, and one metric count names the identity

### Requirement: A restart keeps what stops the Service
The Service SHALL keep its halt, the GitHub requests of its budget window and its ledger of failed rounds in files in the `roadmap` directory of its data directory, beside each repository's `schedule.json`, and a Service that starts SHALL read them back. A Service that starts halted SHALL count the refusal once. A file that exists and cannot be read SHALL stop the start with an error that names the file.

#### Scenario: A restart over the same volume
- **WHEN** a Service halts after 60 requests in the window, a job fails its limit of rounds, and a new Service starts over the same directory with its request count and its metrics at zero
- **THEN** the new Service is halted, its refusal counter is 1, its budget has spent 60 requests, and the job does not run at the next poll

#### Scenario: A record that cannot be read
- **WHEN** the budget record or the ledger record holds text that is not a record
- **THEN** the start fails with an error whose details name the file

### Requirement: A rate limit holds every worker
When a GitHub request of one worker meets a rate limit, no worker SHALL send a GitHub request of the identity before the wait that the rate limit asks for ends, also when the request is not sent again because its retries are spent.

#### Scenario: A secondary limit with retry-after
- **WHEN** one worker's request gets a 403 with `retry-after: 60` and another worker then sends a request
- **THEN** the first worker waits 60 s before its retry, and the other worker's request waits until those 60 s end

#### Scenario: The last rate limit of a request
- **WHEN** one worker's request meets a secondary limit at each attempt, through the session with `retry-after: 60` or through gh, its round fails when its retries are spent, and another worker then sends a request
- **THEN** the other worker's request waits at least 60 s after the last refusal

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

### Requirement: The Service limits its model calls to a configured count in flight
The Service SHALL keep at most `service.model_call_concurrency` model calls in flight at once, default 1, and a lane that cannot take a slot SHALL wait in the Service's process, where no stall timer runs, until it takes one. The Service SHALL set the limit from its setting at start.

#### Scenario: Two lanes send a model call at the same time
- **WHEN** the Service has a limit of 1, two lanes each send a slow model call at the same time, and each call holds its slot while it sends
- **THEN** at most one call is in flight at once, and both calls finish

#### Scenario: A lane waits for a held slot
- **WHEN** the Service has a limit of 1, one call holds the slot, and a lane sends a model call
- **THEN** the lane waits in the process and sends its call once the other call releases the slot

#### Scenario: The limit is raised
- **WHEN** the Service has a limit of 2, four lanes each send a slow model call at the same time, and each call holds its slot while it sends
- **THEN** at most two calls are in flight at once, and all four calls finish
