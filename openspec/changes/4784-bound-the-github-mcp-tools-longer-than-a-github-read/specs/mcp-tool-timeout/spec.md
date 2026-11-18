## ADDED Requirements

### Requirement: Each GitHub MCP tool waits longer than a GitHub read
The MCP server SHALL dispatch the command of each `gh` and `pr` tool of `CONST_MCP_EXPOSURE_TABLE` with the bound `CONST_MCP_GITHUB_TOOL_TIMEOUT_SECONDS`, which is longer than the GitHub session read bound `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS`. Thus a GitHub read in the command stops before the dispatch, and the tool gets the error of the read.

#### Scenario: Each GitHub tool gets the bound around a GitHub read
- **WHEN** the test reads every `gh` and `pr` row of `CONST_MCP_EXPOSURE_TABLE`
- **THEN** each row's timeout equals `CONST_MCP_GITHUB_TOOL_TIMEOUT_SECONDS` and is above `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS`
