# Proposal: #4784

## Why

The GitHub session stops a read at `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` (60 s) (#4626). The `gh` and `pr` MCP tools of `CONST_MCP_EXPOSURE_TABLE` read GitHub, and many hold a dispatch bound of 60 s or 30 s. The dispatch can then stop first with exit code 124 `Command timed out`, and the `GitHubUnreadError` of the read is lost. The owner rule of 2026-11-11 asks each inner bound to be shorter than the call around it, with a margin. Closes #4784.

## What Changes

- Add `CONST_MCP_GITHUB_TOOL_TIMEOUT_SECONDS` (300.0) to `src/devops_cli/config/constants.py`.
- Set the timeout of every `gh` and `pr` row of `CONST_MCP_EXPOSURE_TABLE` to that constant, so each dispatch outlasts the GitHub read with a 240 s margin.
- Extend `tests/github/test_github_session_timeouts.py` to check each `gh` and `pr` row against the constant and the session read bound.

## Capabilities

- Modified: `mcp-tool-timeout`, with a requirement for each `gh` and `pr` MCP tool.

## Impact

- A GitHub read inside a `gh` or `pr` MCP tool fails first with its `GitHubUnreadError`, and the dispatch does not stop it with exit code 124.
- The change fits one pull request.

## Feasibility

- Read 2026-11-18: the `gh` and `pr` rows of `CONST_MCP_EXPOSURE_TABLE` hold 60.0, 30.0, 210.0 and 180.0; `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` is 60.0 and `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS` is 300.0. Every `gh` and `pr` command sends at least one GitHub request, and a write command reads before it writes.

## Existing Tool Considered

No open, maintained library covers a project-specific MCP timeout table. The change edits one constant, the `gh` and `pr` rows and the existing chain test, in one pull request.
