## RENAMED Requirements

- FROM: `### Requirement: The README lists the kept engines`
- TO: `### Requirement: The cluster document lists the kept engines`

## MODIFIED Requirements

### Requirement: The cluster document lists the kept engines
The list of engines in `docs/CLUSTER.md` SHALL name the same engines as `keep_only`.

#### Scenario: The README lists other engines than the settings
- **WHEN** a test reads the sentence "The engines." of `docs/CLUSTER.md` and `keep_only`
- **THEN** the names in backticks in the sentence equal the names in `keep_only`
