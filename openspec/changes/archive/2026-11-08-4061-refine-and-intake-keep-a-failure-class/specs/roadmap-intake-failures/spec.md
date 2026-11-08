## ADDED Requirements

### Requirement: The intake record keeps the failure of a placement
After the writes of a round, the Service SHALL record each candidate whose placement failed in `IntakeRecord.failed`, by number, with the step `place`, the failure class, the count of failures and the time of the last one. A repeat SHALL add 1 to the count. A candidate that is placed, or that is no candidate any more, SHALL have no entry. A candidate with a changed Item SHALL have no entry. The item record SHALL get no mark. A record file with no `failed` field SHALL load with an empty `failed`.

#### Scenario: A placement fails
- **WHEN** the label write of one of three candidates raises `GitHubOperationError`
- **THEN** the intake record holds an entry for it with the step `place`, the class `ci_infra`, the count 1 and the time of the round, and no job wrote to the issue

#### Scenario: The candidate fails again
- **WHEN** the candidate fails again after its wait
- **THEN** the entry holds the count 2 and the new time

#### Scenario: An old record
- **WHEN** a record file from before the field loads
- **THEN** its candidates stay and `failed` is empty

### Requirement: A candidate with a recorded failure waits
A round of the Service, and a scoped update of one issue, SHALL leave a candidate out until `failed_at` plus the wait of its class, before the model is asked. The round SHALL make no triage call and no embedding call for it, SHALL list its number in `IntakePlan.held`, and SHALL not make intake due for it. `devops roadmap intake` keeps no record and waits for nothing.

#### Scenario: The wait has not passed
- **WHEN** a round runs 30 minutes after the failure of a candidate
- **THEN** the model is not asked about it, the candidate is not placed and its entry stays

#### Scenario: The wait has passed
- **WHEN** a round runs 2 hours after the failure
- **THEN** intake decides the candidate and places it, and the entry is removed

#### Scenario: A delivery inside the wait
- **WHEN** a webhook delivery names the candidate 30 minutes after the failure
- **THEN** the update makes no model call
