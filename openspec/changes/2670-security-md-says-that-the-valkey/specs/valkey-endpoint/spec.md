## ADDED Requirements

### Requirement: Security policy states the Valkey MCP tool input rule
SECURITY.md SHALL state that six of the nine `devops valkey` commands are MCP tools, that those tools publish no `url` option, and that a person types `--url` at the command line.

#### Scenario: Policy names the six MCP tools
- **WHEN** A test reads the `--url` paragraph under principle 11 of `SECURITY.md`
- **THEN** The paragraph names `valkey_ping`, `valkey_stats`, `valkey_info`, `valkey_get`, `valkey_set` and `valkey_flush` as MCP tools

#### Scenario: Policy states that the tools publish no url option
- **WHEN** A test reads the `--url` paragraph under principle 11 of `SECURITY.md`
- **THEN** The paragraph states that the six MCP tools publish no `url` option

#### Scenario: Policy states that a person types --url
- **WHEN** A test reads the `--url` paragraph under principle 11 of `SECURITY.md`
- **THEN** The paragraph states that a person types `--url` at the command line and no model gives the URL

#### Scenario: Policy holds no false claim
- **WHEN** A test searches `SECURITY.md` for the sentence `Those commands are not MCP tools.`
- **THEN** The search finds no match
