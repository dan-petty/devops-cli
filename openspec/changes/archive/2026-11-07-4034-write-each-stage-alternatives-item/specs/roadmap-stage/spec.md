## ADDED Requirements

### Requirement: A stage round writes each item when the item is done
A stage round SHALL plan one selected item, write its result, and only then plan the next item. The result is the publish of a ready change, the return of a blocked item, or the stop comment of an item over the budget. A kill of the worker SHALL lose at most the item in progress.

#### Scenario: Kill between item 1 and item 2
- **WHEN** a round selects 3 items and the model call of item 2 raises a `BaseException` that no handler catches
- **THEN** item 1 has its pushed branch, its draft pull request, its record and its comment, and items 2 and 3 have no branch, no record and no comment

### Requirement: A stop ends a stage round after it records the finished items
A stop of the Service or rejected GitHub credentials SHALL end a stage round. The round SHALL record the failure of each item that failed before the stop, and SHALL keep the written result of each finished item. Any other error SHALL be the failure of one item, and the round SHALL go on.

#### Scenario: Stop of the Service in item 3
- **WHEN** item 1 is staged, the plan of item 2 fails, and the Service stops in the plan of item 3 of 4 items
- **THEN** item 1 stays staged, item 2 has a failure record, items 3 and 4 have no record and no comment, and the round ends with the stop

### Requirement: A stage round writes the unselected items first
A stage round SHALL write the removals of closed items and the rejections of items that it does not select before its first plan call. A rejection of a selected item SHALL be written after the plan of that item and before its publish. The round SHALL read the moved paths of an item just before it publishes that item.

#### Scenario: Removal and rejection of unselected items
- **WHEN** a round has a closed item with a staged branch, an item with a rejected plan that the round leaves out, and one item to plan
- **THEN** the removal and the rejection are written before the first plan call

#### Scenario: Rejection of a selected item
- **WHEN** a person names an item whose plan pull request was closed with no merge
- **THEN** the rejection is written after the plan of the item and before its publish, the staged branch of the rejected plan is deleted before the new push, and the Status of the item stays Ready

#### Scenario: A commit lands during the plan of item 2
- **WHEN** a commit that changes a path named by both plans lands on the default branch during the plan of item 2
- **THEN** the comment of item 1 lists no moved path and the comment of item 2 lists the path

### Requirement: A stage plan writes nothing
`devops roadmap stage --plan` SHALL make no write to GitHub or to the remote repository, also when the round holds a removal or a rejection.

#### Scenario: Plan only
- **WHEN** the command runs with `--plan` on a roadmap that holds a removal, a rejection and a ready item
- **THEN** the store receives no write, no branch is pushed or deleted, and no GitHub write request is sent
