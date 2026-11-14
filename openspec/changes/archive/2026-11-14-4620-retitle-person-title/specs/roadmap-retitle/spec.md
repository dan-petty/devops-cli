## MODIFIED Requirements

### Requirement: A run is bounded
The repair pass SHALL examine at most `--limit` items, the lowest numbers first, and SHALL report how many items with a long title or an unlisted type wait.

#### Scenario: Limit of one
- **WHEN** two items have a long title and the limit is 1
- **THEN** the pass changes the lower-numbered item and the report counts one more item

### Requirement: Skip mark
When the repair pass leaves an item with a long title or an unlisted title type, it SHALL write the mark `retitle.skipped` in the job record of the item, once, with one write. The value SHALL be a hash of the title, the body and the `stage.pr` mark that the decision read. This covers an item whose title a person changed, a Planned item without a usable plan title, and an item for which the model gave no summary that passes `title_problems` in two tries. The pass SHALL write no mark for an item that it retitles.

#### Scenario: The model gives no usable summary
- **WHEN** both replies of the model fail `title_problems` and the pass runs with `--confirm`
- **THEN** the job record of the item holds `retitle.skipped`, and the pass wrote that mark once

#### Scenario: A person changed the title
- **WHEN** a person renamed an item after the last job comment and the pass runs with `--confirm`
- **THEN** the job record of the item holds `retitle.skipped`

#### Scenario: The title is changed
- **WHEN** the pass retitles an item
- **THEN** the pass writes no `retitle.skipped` for it
