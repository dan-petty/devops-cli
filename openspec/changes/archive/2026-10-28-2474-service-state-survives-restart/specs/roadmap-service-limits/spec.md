# Spec Delta

## MODIFIED Requirements

### Requirement: A refused identity stops the Service
When a round fails because GitHub refused the Service's identity, the Service SHALL start no round for any repository or lane, also after a restart, until a person removes its halt record and restarts it, SHALL send no later job of the failed round, and SHALL report the refusal once with one error log line and one count of `devops_cli_service_identity_refused_total` that name the identity.

#### Scenario: A suspended account
- **WHEN** a job fails with `gh: Sorry. Your account was suspended. (HTTP 403)` and triggers keep arriving for every repository
- **THEN** no other job starts, and exactly one error line and one metric count name the account

#### Scenario: Another failure
- **WHEN** a round fails for a reason that is not a refused identity
- **THEN** the Service starts later rounds as usual

## ADDED Requirements

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
When a GitHub request of one worker meets a rate limit, no worker SHALL send a GitHub request of the identity before the wait for that request's retry ends.

#### Scenario: A secondary limit with retry-after
- **WHEN** one worker's request gets a 403 with `retry-after: 60` and another worker then sends a request
- **THEN** the first worker waits 60 s before its retry, and the other worker's request waits until those 60 s end
