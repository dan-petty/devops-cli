## ADDED Requirements

### Requirement: The golden set holds a case of a dropped caller
The golden set SHALL hold a case whose issue names a caller and whose recorded plan gives no coverage entry for it, and the replay SHALL refuse the plan with a problem that quotes the caller.

#### Scenario: The replay refuses the dropped caller
- **WHEN** The replay runs the gates on the case of #3170.
- **THEN** The `coverage` gate returns one problem that quotes `devops pr ready`.

#### Scenario: A recorded plan maps every ID
- **WHEN** The replay runs the gates on a recorded plan that holds a coverage entry for each ID of its issue.
- **THEN** The `coverage` gate returns no problem for the plan.
