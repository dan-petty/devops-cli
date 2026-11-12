## MODIFIED Requirements

### Requirement: A job role holds only the read-only tools that its table names
A job role SHALL hold a tool only when the role table names it and the exposure table marks it read-only. A tool that no table names, or that is not read-only, SHALL be unknown on every job endpoint, so a call by name SHALL fail before any handler runs. A name in a table that no tool carries SHALL stop the server from starting.

#### Scenario: A mutating tool called by name
- **WHEN** a client with the token calls `gh_issue_create` on `/planning/mcp`
- **THEN** the result is an error that names an unknown tool, and no command runs

#### Scenario: A tool outside the role
- **WHEN** a client calls `k8s_pods` on `/review/mcp`
- **THEN** the result is an error that names an unknown tool

#### Scenario: A table names a tool that does not exist
- **WHEN** a role table names a tool that the catalogue lacks
- **THEN** building the role server raises an error that names the tool
