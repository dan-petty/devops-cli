## ADDED Requirements

### Requirement: The plan reader reads the identifiers that a group adds
`read_change` SHALL set the `adds` field of a `StageGroup` from the `Adds:` line of its group, in file order. It SHALL raise `PlanReadError` when the line holds a name outside a code span or holds no code span, and SHALL read a group with no `Adds:` line with an empty `adds`.

#### Scenario: A change folder with an Adds line
- **WHEN** the tasks file of a `behavior` group holds `Adds:` with `_delivery_title` in a code span
- **THEN** `read_change` returns that group with `adds` equal to the one name `_delivery_title`

#### Scenario: A malformed Adds line
- **WHEN** a group holds `Adds:` with `_delivery_title` and no code span
- **THEN** `read_change` raises `PlanReadError` with the reason of the line
