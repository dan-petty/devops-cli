# Spec Delta

## ADDED Requirements

### Requirement: The plan lists the items that matched no filter when asked
`stage --plan` SHALL list, under "Matched no filter" and only with `--why`, each open item that the filter does not name. Each line SHALL name the family that the item misses, the values the filter takes, and the value the item has. The section SHALL not be part of "Left out". Without `--why`, the output SHALL not change.

#### Scenario: Why
- **WHEN** the filter is `priority=p0-critical` and a Ready P1 item exists
- **THEN** `stage --plan --why` lists the P1 item under "Matched no filter" with the family `priority`

#### Scenario: No why
- **WHEN** the same plan runs without `--why`
- **THEN** the output has no section "Matched no filter"
