## Purpose

Defines when the roadmap Service stops, holds or skips its GitHub work, so a refused identity, a spent hourly budget or a job that fails at each round never makes the Service send requests without bound.

## ADDED Requirements

### Requirement: A refused identity stops the Service
When a round fails because GitHub refused the Service's identity, the Service SHALL start no round for any repository or lane until it is restarted, SHALL send no later job of the failed round, and SHALL report the refusal once with one error log line and one count of `devops_cli_service_identity_refused_total` that name the identity.

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
