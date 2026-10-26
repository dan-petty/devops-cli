# Spec Delta

## ADDED Requirements

### Requirement: A part is not compared with the other sub-issues of its source
When the source of a new candidate links an issue of the repository, intake SHALL leave that issue and every sub-issue of it out of the items it compares with the candidate. A candidate with no such source SHALL be compared with all items as before.

#### Scenario: A sibling part with a near-identical title
- **WHEN** the source of a new candidate links an issue, and a sub-issue of that issue has a title that is near-identical to the title of the candidate
- **THEN** the items sent to the model for the candidate hold no sub-issue of the source, and the candidate names no possible duplicate

#### Scenario: A sub-issue of another issue
- **WHEN** an item with a near-identical title is a sub-issue of an issue that is not the source of the candidate
- **THEN** the items sent to the model hold that item

#### Scenario: A candidate with no source
- **WHEN** a new candidate has no source, and an item with a near-identical title is a sub-issue of some issue
- **THEN** the items sent to the model hold that item

#### Scenario: A sub-issue whose parent is in another repository
- **WHEN** an item is a sub-issue of an issue that has the number of the source issue but is in another repository
- **THEN** the items sent to the model hold that item
