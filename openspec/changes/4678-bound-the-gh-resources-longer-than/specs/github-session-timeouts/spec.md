## MODIFIED Requirements

### Requirement: Each bound around a GitHub read is shorter than the call around it
In each chain of bounds around a GitHub read, each bound SHALL be shorter than the next one. The chain of the implement job is `DEFAULT_VALKEY_TIMEOUT_SECONDS`, `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` and `DEFAULT_ROADMAP_IMPLEMENT_MONITOR_TIMEOUT_SECONDS`. The chain of a `resource://gh/` resource of the MCP server is `DEFAULT_VALKEY_TIMEOUT_SECONDS`, `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` and `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`.

#### Scenario: The defaults make a chain
- **WHEN** the test reads the defaults of each chain
- **THEN** each one is shorter than the next one in its chain

#### Scenario: An MCP read of a gh resource waits longer than a session read
- **WHEN** the test reads `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` and `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`
- **THEN** the session read timeout is shorter than the MCP bound

#### Scenario: An inner bound that is not shorter fails the chain
- **WHEN** the session read timeout is 3,600 s, the same as the watch of the checks
- **THEN** the chain test fails for that pair
