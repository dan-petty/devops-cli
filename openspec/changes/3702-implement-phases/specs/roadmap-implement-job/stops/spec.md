## ADDED Requirements

### Requirement: A false premise returns the item to New with no push
When a step stops with a `premise` request whose evidence is not empty, the agent phase SHALL end the run with the outcome `returned` and the evidence, and `publish` SHALL return the item to New through `apply_return`, with a comment that holds the evidence masked and cut. The run SHALL push nothing. A return SHALL clear `implement.group`, `implement.sha`, `implement.branch` and `implement.pr`. It SHALL NOT set `implement.stopped`.

#### Scenario: A false premise on a Planned item
- **WHEN** the first step of a Planned item ends with a `premise` request and evidence
- **THEN** the Status is New, the comment holds the evidence, `origin` has no branch for the item, and the record has no `implement.stopped`

#### Scenario: A false premise on a Staged item
- **WHEN** the step of group 2 of a Staged item ends with a `premise` request, and group 1 passed in this run
- **THEN** the Status is New, `origin` holds the staged branch at the commit it had before the run, and `implement.group` is cleared

#### Scenario: A premise request with no evidence
- **WHEN** the `premise` request has an empty `evidence`
- **THEN** the item is stopped as a question and its Status is Blocked

## REMOVED Requirements

### Requirement: A return withdraws the checkpoints first
**Reason**: No run pushes before `publish`, so a return has no checkpoint to take back (#3702).
**Migration**: None.

### Requirement: A false premise returns the item to New
**Reason**: No run pushes before `publish`, so a return has no checkpoint to take back (#3702).
**Migration**: The requirement "A false premise returns the item to New with no push" replaces it.
