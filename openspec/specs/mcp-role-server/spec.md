# mcp-role-server Specification

## Purpose
The streamable HTTP transport of `devops mcp serve` serves one endpoint for each job role, behind one bearer token, so a job reaches only the read-only tools of its role.

## Requirements

### Requirement: The HTTP transport serves one endpoint for each job role
`devops mcp serve --transport streamable-http` SHALL serve `/planning/mcp`, `/implementation/mcp` and `/review/mcp`. Each path SHALL be a separate server that holds only the tools of its role. The `ops` role and any other path SHALL have no endpoint and give 404.

#### Scenario: Two roles list different tools
- **WHEN** a client with the token lists the tools of `/planning/mcp` and of `/review/mcp`
- **THEN** the lists differ, and `review` holds fewer tools than `planning`

#### Scenario: A path that is no job role
- **WHEN** a client with the token posts to `/ops/mcp` or to `/mcp`
- **THEN** the answer is 404

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

### Requirement: A connection shares no state with another connection
A role server SHALL offer no resource, no prompt and no `hydrate_tool_domain`. The tools of a role SHALL not change when a caller hydrates a domain on the stdio server. The endpoints SHALL be stateless.

#### Scenario: Hydration does not leak
- **WHEN** a client hydrates the `docker` domain on the stdio server
- **THEN** the tool list of every role endpoint is the same as before

### Requirement: The remote transport needs a bearer token to start
The `streamable-http` transport SHALL refuse to start, and its dry run SHALL refuse, when the `mcp.token` credential is unset or has fewer than 32 characters. It SHALL refuse a host that is not loopback unless `--allow-remote` is set.

#### Scenario: No token
- **WHEN** a user runs `devops mcp serve --transport streamable-http` with no `DEVOPS_CLI_MCP_TOKEN`
- **THEN** the command exits 1 with an error that names `mcp.token`, and no server starts

#### Scenario: A short token
- **WHEN** the token has 5 characters
- **THEN** the start is refused with an error that names the minimum length

### Requirement: A request without the token is refused before a tool runs
Every request to a role endpoint SHALL carry `Authorization: Bearer <token>`. The server SHALL compare the token in constant time and SHALL answer 401 with a `WWW-Authenticate: Bearer` header for a missing, wrong or non-bearer credential, before any tool runs.

#### Scenario: A wrong token
- **WHEN** a client posts a `tools/call` with a wrong token
- **THEN** the answer is 401, and the audit log holds no tool call

#### Scenario: No token
- **WHEN** a client posts a `tools/list` with no `Authorization` header
- **THEN** the answer is 401

### Requirement: Each tool call is logged with its role and no argument
The server SHALL log the role and the tool name of each call, including a call that the argument contract refuses, and SHALL log no argument value.

#### Scenario: A call is logged
- **WHEN** a client calls `pr_diff` on `/review/mcp`
- **THEN** the log holds `MCP tool call: role=review tool=pr_diff` and no argument

### Requirement: A read-only tool publishes no option that writes
A tool that the exposure table marks read-only SHALL publish no option whose description holds `resolve`, `write`, `delete` or `create`. The word SHALL count as a whole word in its base, `-s` or `-ing` form and in any letter case. A past form such as `resolved` SHALL NOT count.

#### Scenario: A read-only tool with a writing option
- **WHEN** A test reads the published schema of a read-only tool, and one option description is `Write findings to this path.`
- **THEN** The test reports the tool and the option.

#### Scenario: A tool that is not read-only
- **WHEN** A test reads the published schema of a tool that is not read-only, and one option description is `Automatically resolve review threads.`
- **THEN** The test reports nothing.

#### Scenario: A past form of a write verb
- **WHEN** A test reads the published schema of a read-only tool, and one option description is `Inherited policies are resolved via 'extends'.`
- **THEN** The test reports nothing.

#### Scenario: The published tools
- **WHEN** A test reads the published schema of every tool that the server registers
- **THEN** No read-only tool has an option that the rule reports.

### Requirement: A tool that keeps a writing option is not read-only
The tools `pr_check_readiness`, `roadmap_refine`, `roadmap_run` and `ci` SHALL be marked not read-only. They SHALL publish the options `auto_resolve`, `confirm`, `confirm` and `fix` respectively. The command `devops pr check-readiness` SHALL keep the option `--auto-resolve`.

#### Scenario: The readiness tool
- **WHEN** A test reads the published tool `pr_check_readiness`
- **THEN** Its read-only flag is false, and its schema holds `auto_resolve`.

#### Scenario: The refine, run and ci tools
- **WHEN** A test reads the published tools `roadmap_refine`, `roadmap_run` and `ci`
- **THEN** All three read-only flags are false, and the schemas hold `confirm`, `confirm` and `fix`.

#### Scenario: The readiness command
- **WHEN** A test reads the options of `devops pr check-readiness`
- **THEN** The options include `--auto-resolve`.

### Requirement: A read-only tool publishes no option for a file that its command writes
The tools `scan_injection` and `tf_plan` SHALL be marked read-only. They SHALL publish no `sarif` option and no `out` option. The commands `devops scan injection` and `devops tf plan` SHALL keep the options `--sarif` and `--out`.

#### Scenario: The published injection scan and plan tools
- **WHEN** A test reads the published tools `scan_injection` and `tf_plan`
- **THEN** Both read-only flags are true, and the schemas hold no `sarif` property and no `out` property.

#### Scenario: The injection scan and plan commands
- **WHEN** A test reads the options of `devops scan injection` and `devops tf plan`
- **THEN** The options include `--sarif` and `--out`.
