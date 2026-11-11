## ADDED Requirements

### Requirement: An MCP tool mirrors the plan run
The MCP tool `roadmap_consolidate` SHALL publish only `repo`, `ref`, `limit` and `dry_run`, SHALL set `readOnlyHint` to true, and its argv MUST NOT hold `--apply`, `--confirm` or `--decline`. No due-table row of the Service run SHALL start the job.

#### Scenario: A client calls the tool with every published option
- **WHEN** a client calls `roadmap_consolidate` with no option, and then with `repo`, `ref`, `limit` and `dry_run`
- **THEN** the argv of each call is `devops roadmap consolidate` with only those options, and it holds no write flag
