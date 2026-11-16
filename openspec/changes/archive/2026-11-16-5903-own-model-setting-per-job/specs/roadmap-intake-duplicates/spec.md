# Spec Delta

## MODIFIED Requirements

### Requirement: An evaluation run takes intake's verdict for each case
`devops roadmap eval intake` SHALL run each case of the intake duplicate evaluation set through intake with the model of the task `intake`, one case at a time, and SHALL write nothing. For each case it SHALL seed a roadmap that holds the case's item as an item and plan intake for the case's candidate. The verdict SHALL be `duplicate` when the decision names the item as the possible original, `skipped` when intake skips the candidate, and `new item` otherwise.

#### Scenario: A reply that names the item with no shared change
- **WHEN** the model names the case's item as the original of a candidate and gives no shared change
- **THEN** the verdict of that case is `new item`

### Requirement: An evaluation dry run makes no request
`devops roadmap eval intake --dry-run` SHALL make no request and SHALL list each case with the one `intake` call that a run makes for it.

#### Scenario: The dry run of the set
- **WHEN** `devops roadmap eval intake --dry-run` runs
- **THEN** it lists the 16 cases and 16 `intake` calls, and the model gets no call
