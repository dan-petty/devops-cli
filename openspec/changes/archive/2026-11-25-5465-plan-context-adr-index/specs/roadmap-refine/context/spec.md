## ADDED Requirements

### Requirement: The refine context holds a one-line index of ADRs in force
`collect_context` SHALL list each ADR in force at the staged commit as `ADR NNNN: <title>` in number order under one heading instructing `read_file` on `docs/adr/`, omitting superseded text, and SHALL omit the heading when none is in force.

#### Scenario: Superseded and accepted ADRs in one commit
- **WHEN** the commit holds accepted and superseded ADRs under `docs/adr/`
- **THEN** the context lists only ADRs in force under one heading naming `read_file` and `docs/adr`, with no full ADR body text
