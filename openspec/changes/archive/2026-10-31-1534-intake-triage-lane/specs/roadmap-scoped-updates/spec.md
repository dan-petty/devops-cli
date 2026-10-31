# Spec Delta

## MODIFIED Requirements

### Requirement: An issues delivery runs intake of its one issue
`run_scoped_update` SHALL run intake of the one issue that a delivery of the `issues` event with the action `opened`, `edited` or `reopened` names, on the triage lane, with intake's own decision code. It SHALL decide and write nothing for another issue.

#### Scenario: A delivery about one of three candidates
- **WHEN** a delivery of `issues` with the action `opened`, `edited` or `reopened` names candidate 2 of three candidates
- **THEN** the model judges candidate 2 alone, and only candidate 2 gets labels and a reason comment

#### Scenario: An edit of an issue that is already an Item
- **WHEN** a delivery of `issues` `edited` names an issue that holds a `priority/*` label, and no other candidate is open
- **THEN** the model judges nothing, the store records no write, and no intake record is written
