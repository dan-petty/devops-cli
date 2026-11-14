## MODIFIED Requirements

### Requirement: Criteria mapping in the stage reply
The stage reply SHALL hold a `criteria` list in which each entry gives the text of one acceptance criterion of the issue and either the number of the group that delivers it or `pending-person` with a reason. An acceptance criterion SHALL be a top-level item of a list under a heading `Acceptance criteria` in the text of the issue body that a person wrote, before the block of the refine job. An issue with no such list SHALL have no criterion.

#### Scenario: Every criterion is mapped
- **WHEN** The issue has three acceptance criteria and the reply's `criteria` list holds an entry for each, with a group number or `pending-person` and a reason
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: The list of the refine block is not read
- **WHEN** The issue body holds a list under `Acceptance criteria` in the refine block as well, and the reply maps the items of the list that a person wrote
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: The issue has no acceptance list
- **WHEN** The issue body has no heading `Acceptance criteria` and the reply's `criteria` list is empty
- **THEN** `check_proposal` returns no problem for the criteria mapping

#### Scenario: A pending-person entry has no reason
- **WHEN** An entry of `criteria` gives `pending-person` and a blank reason
- **THEN** the reply breaks the schema and goes back to the model
