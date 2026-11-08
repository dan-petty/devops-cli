## Purpose
Client integration connecting roadmap stage and implement jobs to role-scoped remote MCP tools over streamable HTTP.

## ADDED Requirements

### Requirement: MCP settings
The settings SHALL define `roadmap.mcp.url`, `roadmap.stage.mcp` and `roadmap.implement.mcp`, with both switches false by default.

#### Scenario: Default MCP settings
- **WHEN** No configuration sets the MCP URL or a switch.
- **THEN** Both switches load as false and the URL loads as unset.

### Requirement: Remote tools join the toolset
When a job's MCP switch is true, the job MUST add its role's remote tools through the pydantic-ai MCP client.

#### Scenario: Stage job with MCP on
- **WHEN** `roadmap.stage.mcp` is true and the fake MCP server offers a tool.
- **THEN** The stage agent can call that remote tool beside its local tools.

### Requirement: Local tools win
A local tool MUST win when a remote tool has the same name.

#### Scenario: Remote name clash
- **WHEN** The fake MCP server offers a tool with the name of a local tool.
- **THEN** The agent calls the local tool and the remote tool is not added under that name.

### Requirement: Remote call bounds
Each remote MCP call MUST use `roadmap.mcp.timeout_seconds` and MUST count in the job's tool-call limit.

#### Scenario: Remote call exceeds timeout
- **WHEN** A fake remote tool sleeps past that timeout.
- **THEN** The call fails as a tool error and the run trace records the timeout.

### Requirement: Remote call trace
The run trace MUST record each remote MCP call, its result and its timeout.

#### Scenario: Trace after a remote call
- **WHEN** A job with MCP on makes one remote call.
- **THEN** The `RunTrace` holds one entry for that remote call.

### Requirement: Remote failure is a tool error
A failure of a remote MCP call MUST reach the model as a tool error and MUST NOT stop the job.

#### Scenario: Remote tool fails
- **WHEN** The fake MCP server returns an error for a remote tool call.
- **THEN** The model receives the error text and the job continues.

### Requirement: Server down at start
When the MCP server is unavailable at job start, the job MUST stop with a class that names the MCP server.

#### Scenario: Server unavailable at start
- **WHEN** The fake MCP server refuses the first connection.
- **THEN** The job raises `RoadmapMcpUnavailableError` with the server URL.

### Requirement: Credential and role
The job MUST send the MCP bearer token for its role.

#### Scenario: Stage job authenticates
- **WHEN** The stage job connects with MCP on.
- **THEN** The fake server receives `mcp.stage_token` and grants the stage role.

### Requirement: Offline tests
The tests MUST use an in-process fake MCP server and MUST make no network request.

#### Scenario: Offline test run
- **WHEN** The roadmap MCP tests run with no network.
- **THEN** The fake server answers every MCP call and no socket opens.

### Requirement: Eval score
The change MUST report the stage and implement eval scores with and without the remote tools.

#### Scenario: Eval comparison
- **WHEN** The stage and implement evals run with MCP off and on.
- **THEN** The change records both scores and the difference.
