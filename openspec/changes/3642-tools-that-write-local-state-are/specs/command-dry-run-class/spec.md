## MODIFIED Requirements

### Requirement: mcp-read-only-hint-agrees-with-no-external-request
The `no-external-request` class SHALL name external requests only. An entry of `CONST_MCP_EXPOSURE_TABLE` for a `no-external-request` command SHALL set `readOnlyHint` false when the command writes local state or a file, and true when it writes neither. The ratchet test SHALL name each such command that writes, and SHALL fail on a flag that disagrees.

#### Scenario: mcp tool wraps no-external-request command
- **WHEN** an MCP tool definition in `CONST_MCP_EXPOSURE_TABLE` maps to a command path with `no-external-request`, and the command writes no local state and no file
- **THEN** the third element of the table entry is `True`

#### Scenario: a local writer has a tool that is not read-only
- **WHEN** a test reads the entries of `ai quiesce`, `ai resume`, `ai failover`, `ai gateway failover`, `review export-feedback` and `ai ingest library` in `CONST_MCP_EXPOSURE_TABLE`
- **THEN** the third element of each entry is `False`

#### Scenario: a local writer marked read-only fails
- **WHEN** the ratchet audits a table in which the entry of a `no-external-request` command that writes local state is read-only
- **THEN** the audit reports that command

#### Scenario: a command that writes nothing marked not read-only fails
- **WHEN** the ratchet audits a table in which the entry of a `no-external-request` command outside the set of local writers is not read-only
- **THEN** the audit reports that command
