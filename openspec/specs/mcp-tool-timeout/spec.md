# mcp-tool-timeout Specification

## Purpose
Enforce bounded execution deadlines across in-process and external MCP tool invocations so that hung commands stop within their configured timeout budgets and report clear errors.

## Requirements

### Requirement: Every MCP tool stops at its timeout
The MCP server and dispatcher SHALL enforce each tool's configured timeout for external and in-process commands. When a command execution exceeds its timeout, the tool SHALL return or raise a timeout error naming the tool command.

#### Scenario: An in-process command exceeds its timeout
- **WHEN** an MCP tool invokes an in-process command that runs longer than its configured timeout
- **THEN** the dispatcher stops waiting within the timeout budget and returns exit code 124 with a message naming the command
