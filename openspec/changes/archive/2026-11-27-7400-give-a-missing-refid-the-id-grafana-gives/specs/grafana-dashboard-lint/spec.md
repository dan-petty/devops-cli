## ADDED Requirements

### Requirement: A target with no refId gets the id that Grafana gives it
The linter SHALL give each target that states no refId the id that Grafana gives it when it loads the panel: the first id in the order A to Z, then AA, AB and so on, that no target of the panel holds. The linter SHALL report a duplicate refId only when two targets of a panel hold the same id after that step.

#### Scenario: Two targets with no refId are no duplicates
- **WHEN** The linter reads a panel with two targets that state no refId.
- **THEN** It reports no "Duplicate target refId" error, because the targets get the ids A and B.

#### Scenario: A stated id is skipped
- **WHEN** The linter reads a panel whose first target states no refId and whose second target states `A`.
- **THEN** The first target gets the id B, and the linter reports no duplicate.

#### Scenario: Two stated ids stay duplicates
- **WHEN** The linter reads a panel with two targets that state `A` and a third that states none.
- **THEN** It reports one error "Duplicate target refId 'A'; a series will be dropped".
