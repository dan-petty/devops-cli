## ADDED Requirements

### Requirement: Refine writes the result of an item with one request
Refine SHALL write the new body, the marks of the job record and the Status of one item with one `PATCH` of the issue, and the comment as a separate request after it. A stop of the Service after the write SHALL leave the new body, the new marks and the new Status together, so the next round SHALL make no model call for the item. The dry-run plan SHALL list one read of the issue and one `PATCH` for the body with the marks, and no separate write of the body.

#### Scenario: A stop after the only write of a Ready item
- **WHEN** a refine round sets a New item Ready and the Service stops right after the write of the item
- **THEN** the item has the refined body, the Status Ready and the marks of the round, and the next round refines no item and makes no model call

#### Scenario: An item that keeps its Status
- **WHEN** refine leaves a New item New with a question for a person
- **THEN** refine makes one write of the issue that holds the new body and the marks, and one comment

#### Scenario: A Ready item goes back to New
- **WHEN** refine finds a Ready item not ready
- **THEN** refine makes one write of the issue that holds the new body, the Status New and the marks, and one comment

#### Scenario: The dry-run plan of a refine round
- **WHEN** `devops roadmap refine --dry-run` plans a round, and a round with `--item 7`
- **THEN** each plan lists one read of the issue and one `PATCH` that carries the body and the labels, and neither plan lists a separate write of the body
