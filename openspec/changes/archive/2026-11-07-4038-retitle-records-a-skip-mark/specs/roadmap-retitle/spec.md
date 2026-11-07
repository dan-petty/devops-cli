## ADDED Requirements

### Requirement: Skip mark
When the repair pass leaves an item with a long title, it SHALL write the mark `retitle.skipped` in the job record of the item, once, with one write. The value SHALL be a hash of the title, the body and the `stage.pr` mark that the decision read. This covers an item whose title a person changed, a Planned item without a usable plan title, and an item for which the model gave no summary that passes `title_problems` in two tries. The pass SHALL write no mark for an item that it retitles.

#### Scenario: The model gives no usable summary
- **WHEN** both replies of the model fail `title_problems` and the pass runs with `--confirm`
- **THEN** the job record of the item holds `retitle.skipped`, and the pass wrote that mark once

#### Scenario: A person changed the title
- **WHEN** a person renamed an item after the last job comment and the pass runs with `--confirm`
- **THEN** the job record of the item holds `retitle.skipped`

#### Scenario: The title is changed
- **WHEN** the pass retitles an item
- **THEN** the pass writes no `retitle.skipped` for it

### Requirement: A skipped item is not selected again
The selection of the repair pass SHALL leave out an open item whose `retitle.skipped` equals the hash of its current title, body and `stage.pr` mark. It SHALL select the item again when its title, its body or its `stage.pr` mark changes. A comment on the item SHALL NOT select it again. A skipped item SHALL NOT hold a place of `--limit`.

#### Scenario: Next round after a skip
- **WHEN** the pass skipped an item and runs again with no change to the item
- **THEN** the selection does not hold the item, and a later item with a long title takes the place of the limit

#### Scenario: The item changes
- **WHEN** the title, the body or the `stage.pr` mark of a skipped item changes
- **THEN** the selection holds the item again

### Requirement: A skipped item costs one write once
A skipped item SHALL cost one write in the round that skips it. In a later round with no change to the item, it SHALL cost no read of its comments, no read of its title changes, no read of a pull request title and no model request.

#### Scenario: Two rounds
- **WHEN** the pass runs twice with `--confirm` on one item that it cannot shorten
- **THEN** the first round makes one write of the mark and the second round makes no write, no read of the item and no model request

### Requirement: Dry run lists the write of the mark
The dry run of the repair pass SHALL list the write of the mark `retitle.skipped` with the condition under which it runs.

#### Scenario: Preview of the writes
- **WHEN** the repair pass runs with `--dry-run`
- **THEN** the planned writes hold one write of the body of an item with a condition for a skipped item
