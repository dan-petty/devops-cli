## ADDED Requirements

### Requirement: Each gh resource waits longer than a GitHub read
The MCP server SHALL dispatch the command of each `resource://gh/` resource with the bound `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`, which is longer than the GitHub session read bound `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS`. Thus a GitHub read in the command stops before the dispatch, and the resource gets the error of the read.

#### Scenario: Each gh resource gets the bound around a GitHub read
- **WHEN** a client reads each of the four `resource://gh/` resources: `pages/status`, `issues/status`, `project/status` and `views/status`
- **THEN** the dispatcher gets the command of each one with the bound `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`
