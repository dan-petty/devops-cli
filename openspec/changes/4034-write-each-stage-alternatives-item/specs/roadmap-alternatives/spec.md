## ADDED Requirements

### Requirement: An alternatives round writes each check when the check is done
An alternatives round SHALL write the body block, the record and the comment of check N before check N+1 starts. A kill of the worker SHALL lose at most the check in progress.

#### Scenario: Kill in item 3 of 5
- **WHEN** a round selects 5 items and the model call of the third item raises a `BaseException` that no handler catches
- **THEN** checks 1 and 2 have their body block, record and comment, and the other items have none

### Requirement: A rate limit ends an alternatives round and keeps the written checks
An alternatives round SHALL end when a write fails with a GitHub rate limit. It SHALL keep the checks that it wrote and SHALL NOT check the items after the failed one.

#### Scenario: Rate limit in check 2
- **WHEN** the write of the body of item 2 of 5 fails with a rate-limit error
- **THEN** the round raises the error, item 1 keeps its written check, and the model gets no request for items 3, 4 and 5

### Requirement: An alternatives plan writes nothing
`devops roadmap alternatives --plan` SHALL make no write to the roadmap store.

#### Scenario: Plan only
- **WHEN** the command runs with `--plan` on 3 items that have no check
- **THEN** the store receives no write
