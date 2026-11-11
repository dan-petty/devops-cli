## ADDED Requirements

### Requirement: Each fix round and each failed item logs one line with counts
The roadmap jobs SHALL log one line with counts and no model text for a stage reply that passes or stays refused after a return, for each stage review round, for each failed stage item with its step and class, and for each ended implement Job with its state, class, repair rounds, tokens and runner digest. Each line SHALL name the repository before the item, and SHALL end with the devops-cli version.

#### Scenario: A pass after a return and two review rounds
- **WHEN** the first review returns a plan, the checks refuse the revision once, and the next revision passes the checks and the review
- **THEN** two `stage review round` lines give the repository, the item, rounds 0 and 1 and their counts, and one `stage gate returns` line gives `returns=1 result=passed`

#### Scenario: A failed item
- **WHEN** a stage round fails an item whose plan the checks refused twice
- **THEN** one `stage item failed` line gives the repository, the item, the step `plan` and the class `plan_defect`

#### Scenario: An implement attempt
- **WHEN** the implement row reports a Job that failed with an out-of-memory log on runner digest `sha256:<a>`
- **THEN** one `implement attempt` line gives the repository, the item, `state=failed class=oom` and that digest

### Requirement: The error line of a round names every failed item
The error line of a failed round SHALL keep the first 256 characters of the first line of each error, and then give the number of each failed item of an error that has failed items.

#### Scenario: A long reason of the first item
- **WHEN** the stage row fails three items and the first line of its error is longer than 256 characters
- **THEN** the error of the round ends with `(failed items: #1, #2, #3)`
