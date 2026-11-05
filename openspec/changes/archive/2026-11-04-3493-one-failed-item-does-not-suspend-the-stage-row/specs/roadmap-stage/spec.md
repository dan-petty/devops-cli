## MODIFIED Requirements

### Requirement: A failure stops one item and never hides the others
A model call that fails SHALL skip its item. The job SHALL stage the other items and record each skipped item in its job record. The command SHALL exit 1 and name each skipped item. Rejected credentials SHALL stop the run. A validation error, such as a timeout, SHALL skip its item the same way. A push that GitHub refuses SHALL stop its item with the reason and leave no remote branch without an open pull request. An item whose text looks like a secret SHALL be left out before the model reads it.

#### Scenario: One model call fails
- **WHEN** the model call fails for the first of two items
- **THEN** the second item is staged, the command exits 1, and the error names the first item

#### Scenario: The validation times out
- **WHEN** the validation of the first of two items runs past its timeout
- **THEN** the second item is planned, and the error names the first item

#### Scenario: Rejected credentials
- **WHEN** the model call fails with rejected credentials for the first item
- **THEN** the run stops and stages no item

#### Scenario: The push is refused
- **WHEN** GitHub refuses the push of a branch
- **THEN** the job stops that item with the reason, opens no pull request and records no staged key

#### Scenario: A secret in the body
- **WHEN** the body of an item holds a text that looks like a secret
- **THEN** the plan leaves the item out, and the model reads none of its text

### Requirement: A failed write stops one item
A write that fails, also the comment on an item stopped on the budget, SHALL stop its item with the reason and SHALL NOT stop the other writes. The job SHALL record each item that failed in its job record, and the command SHALL fail after the other writes and name each item that failed. The labels of the draft pull request are the one exception: a label that GitHub refuses stops no item (requirement "The draft pull request gets the labels of its title").

#### Scenario: The comment of a stopped item fails
- **WHEN** two items stop on the budget and the comment on the first fails
- **THEN** the second item still gets its comment and its record, the first item gets no stop record but gets a failure record, and the error names the first item

### Requirement: The Service runs the stage job on the model lane
The model lane of the Service SHALL hold the row `stage` after the row `refine`. The row SHALL be due by its interval of 60 minutes, on its first run, and in a round where `refine` set an item Ready. The row SHALL run the stage job in the model clone of the lane and write what its plan holds. The row SHALL fail the round only when the round tried items and staged, stopped or returned none, and for a failure that no item explains. `devops roadmap run --dry-run` SHALL list the row when it is due.

#### Scenario: The first run
- **WHEN** a repository has no record of a `stage` round
- **THEN** the row is due, after the rows that come before it

#### Scenario: The interval
- **WHEN** the last success of the row is 61 minutes old and no other trigger exists
- **THEN** the row is due
- **AND** with a last success 59 minutes old, the row is not due

#### Scenario: Refine set an item Ready
- **WHEN** the last success of the row is 5 minutes old and the `refine` row of the same round returned an outcome with `set_ready`
- **THEN** the row is due in that round

#### Scenario: Refine set an item Ready and failed another
- **WHEN** the last success of the row is 5 minutes old and the `refine` row of the same round set one item Ready and failed for another item
- **THEN** the row is due in that round
- **AND** the round still fails for the `refine` row

#### Scenario: Refine set no item Ready
- **WHEN** the last success of the row is 5 minutes old and the `refine` row returned an outcome with no `set_ready`
- **THEN** the row is not due

#### Scenario: The dry run
- **WHEN** `devops roadmap run --dry-run` runs for a repository with no record of a round
- **THEN** its `Due:` line lists `stage` after `refine`, and no request is made

## ADDED Requirements

### Requirement: A failed item is recorded in its job record
When the plan or a write of an item fails, the job SHALL record the time (`stage.failed_at`) and the class of the error (`stage.failed_error`) in the job record of the item. A run that stages the item or stops it on the budget SHALL clear both keys.

#### Scenario: A failure is recorded
- **WHEN** the model call fails for an item with the error class `AIClientError`
- **THEN** the job record of the item holds the time of the round and `AIClientError`

#### Scenario: The item is staged
- **WHEN** a run stages an item whose job record holds a failure
- **THEN** the job record of the item holds neither key afterwards

### Requirement: A failed item waits for the retry delay
The job SHALL leave an item out of the selection until `roadmap.stage.retry_hours` hours (at least 1, default 6) have passed since `stage.failed_at`, and SHALL take the other items in the same round. `--item` SHALL take the item it names. A failure time that is no time SHALL hold the item for no time.

#### Scenario: The delay has not passed
- **WHEN** the item failed 5 hours and 59 minutes ago and the delay is 6 hours
- **THEN** the job leaves the item out and takes the next item

#### Scenario: The delay has passed
- **WHEN** the item failed 6 hours ago and the delay is 6 hours
- **THEN** the job takes the item again

#### Scenario: A person names the item
- **WHEN** the item failed 1 minute ago and a run names it with `--item`
- **THEN** the job takes the item

### Requirement: The row fails only when no item was handled
The stage row SHALL fail a round with the items that failed only when the round tried at least one item and staged, stopped on the budget or returned none of them. A round in which one item failed and another was handled SHALL succeed. A round that tried no item SHALL succeed. An error that belongs to no item, such as a failed read of the repository, SHALL fail the round.

#### Scenario: One item fails and another stages
- **WHEN** three rounds each fail the plan of one item and stage another item
- **THEN** no round fails and the row is not suspended

#### Scenario: Every item fails
- **WHEN** three rounds each try one item and plan none
- **THEN** each round fails and names the item, and the row is suspended

#### Scenario: A failure outside any item
- **WHEN** three rounds each fail with an error that belongs to no item
- **THEN** each round fails and the row is suspended
