## MODIFIED Requirements

### Requirement: Requests stay under an hourly budget
The Service SHALL check `service.github_requests_per_hour` for each GitHub request where the request is sent, SHALL make a request that the last hour has no room for wait until the window has room, SHALL start no round while the window is full, SHALL run the held triggers as one round for each lane of each repository when the window has room, and SHALL poll no faster than the budget pays for at the measured cost of a round.

#### Scenario: A spent budget
- **WHEN** the requests of the last hour are as many as the budget
- **THEN** a trigger that arrives starts no round until an hour has passed since the oldest of those requests

#### Scenario: A round that would pass the budget
- **WHEN** a round has sent requests up to the budget and sends one more
- **THEN** the request waits until the window has room, and the Service sends no more than the budget in any hour

#### Scenario: A costly round
- **WHEN** the rounds of one poll cost more than the budget pays for at the configured interval
- **THEN** the next poll comes after the longer interval that the budget gives

### Requirement: The Service shows its budget and each hold
The Service's `/metrics` SHALL hold `devops_cli_service_budget_limit_requests`, the hourly budget, and `devops_cli_service_budget_spent_requests`, the GitHub requests of the last hour as of the last request or check. The Service SHALL add 1 to `devops_cli_service_budget_holds_total` each time a hold begins.

#### Scenario: A hold that begins, ends and begins again
- **WHEN** a budget of 100 sees 100 requests and two checks, then the window slides past those requests, then 100 more requests and a check
- **THEN** the gauges and the counter read (limit 100, spent 0, holds 0), then (100, 100, 1), then (100, 0, 1), then (100, 100, 2)

### Requirement: A restart keeps what stops the Service
The Service SHALL keep its halt, the GitHub requests of its budget window and its ledger of failed rounds in files in the `roadmap` directory of its data directory, beside each repository's `schedule.json`, and a Service that starts SHALL read them back. The Service SHALL write each request to the budget file when it sends the request, so a pod that stops in the middle of a round loses none. A Service that starts halted SHALL count the refusal once. A file that exists and cannot be read SHALL stop the start with an error that names the file.

#### Scenario: A pod stops in the middle of a round
- **WHEN** the Service sends 3 requests of a round and the pod stops before the round ends
- **THEN** the budget file holds 3 requests, and the Service that starts next has spent 3 requests

#### Scenario: A restart over the same volume
- **WHEN** a Service halts after 60 requests in the window, a job fails its limit of rounds, and a new Service starts over the same directory with its request count and its metrics at zero
- **THEN** the new Service is halted, its refusal counter is 1, its budget has spent 60 requests, and the job does not run at the next poll

#### Scenario: A record that cannot be read
- **WHEN** the budget record or the ledger record holds text that is not a record
- **THEN** the start fails with an error whose details name the file
