## MODIFIED Requirements

### Requirement: The allow-list holds the read-only rows of the exposure table
The builder SHALL hold each command path whose row of `CONST_MCP_EXPOSURE_TABLE` is read-only and whose permitted parameters hold no path parameter, with the permitted parameter names as its value.

#### Scenario: A read-only command with no path parameter
- **WHEN** the builder runs and the row of `gh label list` is read-only and its permitted parameters hold no path parameter
- **THEN** the table holds `('gh', 'label', 'list')` with `repo` among its parameters
