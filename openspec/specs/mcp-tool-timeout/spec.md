# mcp-tool-timeout Specification

## Purpose
Enforce bounded execution deadlines across in-process and external MCP tool invocations so that hung commands stop within their configured timeout budgets and report clear errors.

## Requirements

### Requirement: Every MCP tool stops at its timeout
The MCP server and dispatcher SHALL enforce each tool's configured timeout for external and in-process commands. When a command execution exceeds its timeout, the tool SHALL return or raise a timeout error naming the tool command.

#### Scenario: An in-process command exceeds its timeout
- **WHEN** an MCP tool invokes an in-process command that runs longer than its configured timeout
- **THEN** the dispatcher stops waiting within the timeout budget and returns exit code 124 with a message naming the command

### Requirement: Each gh resource waits longer than a GitHub read
The MCP server SHALL dispatch the command of each `resource://gh/` resource with the bound `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`, which is longer than the GitHub session read bound `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS`. Thus a GitHub read in the command stops before the dispatch, and the resource gets the error of the read.

#### Scenario: Each gh resource gets the bound around a GitHub read
- **WHEN** a client reads each of the four `resource://gh/` resources: `pages/status`, `issues/status`, `project/status` and `views/status`
- **THEN** the dispatcher gets the command of each one with the bound `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`
