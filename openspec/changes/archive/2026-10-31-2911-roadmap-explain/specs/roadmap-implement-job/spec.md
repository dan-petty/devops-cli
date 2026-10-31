# Spec Delta

## ADDED Requirements

### Requirement: The plan lists the items that matched no filter when asked
`implement --plan` SHALL list, under "Matched no filter" and only with `--why`, each open item that the filter does not name. Each line SHALL name the family that the item misses, the values the filter takes, and the value the item has. The section SHALL not be part of "Left out". Without `--why`, the output SHALL not change.

#### Scenario: Why
- **WHEN** the default filter is in force and a Planned item holds `effort/medium`
- **THEN** `implement --plan --why` lists the item under "Matched no filter" with the family `effort`

#### Scenario: No why
- **WHEN** the same plan runs without `--why`
- **THEN** the output has no section "Matched no filter"
