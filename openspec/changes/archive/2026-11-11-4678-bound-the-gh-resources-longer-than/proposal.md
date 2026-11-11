# Proposal: #4678

## Why

The GitHub session waits at most `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` (60 s) for each read (#4626). The MCP server dispatched the command of each of its four `resource://gh/` resources with `DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS` (30 s). `resource://gh/issues/status` runs `devops gh issues status`, which reads the issues of the repository through the GitHub session. When a read gets no answer, the dispatch stops at 30 s with exit code 124 and `Command timed out`, and the `GitHubUnreadError` of the read is lost. The owner rule of 2026-11-11 says that each inner timeout is shorter than the call around it, with a margin. The chain test of #4626 held no MCP bound, so it did not find this. Closes #4678.

## What Changes

- Each of the four `resource://gh/` resources of the MCP server dispatches its command with `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS` (300 s), not with `DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS` (30 s). A listing reads one page for each read, so the bound around it holds more than one read.
- The chain test of the bounds around a GitHub read holds two chains: the watch of the checks of the implement job, and the MCP read of a `resource://gh/` resource. Each pair of a chain is one test case.
- A test reads each `resource://gh/` resource through the dispatcher fake and compares the bound of each dispatch with `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`.
- ADR 0006, the comment of `DEFAULT_GH_SESSION_READ_TIMEOUT_SECONDS` and the rejected alternative of the archived design of #4626 name the calls that the read bound is shorter than.

The bound of an MCP resource is a behavior that a consumer observes (a resource read gets the error of the GitHub read, not a timeout of the dispatch), so the change has a spec delta.

## Capabilities

- `github-session-timeouts` (modified): the chains of bounds around a GitHub read hold the MCP read of a `resource://gh/` resource.
- `mcp-tool-timeout` (modified): each `resource://gh/` resource waits longer than a GitHub session read.

## Impact

- A read of a `resource://gh/` resource can now take up to 300 s, not 30 s. When a GitHub read in it gets no answer, the read fails at 60 s and the resource returns its error.
- No setting, command or manifest changes. The change fits one pull request.

## Feasibility

- Census: `grep -c '@mcp.resource("resource://gh/' src/devops_cli/ai/mcp/server.py` gives 4: `pages/status`, `issues/status`, `project/status` and `views/status`. On main, each one passes `timeout=DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS` (30 s) to `_run_mcp_cmd`.
- Source: `get_issues_summary` (`src/devops_cli/github/issues.py`) reads the items of `GitHubRoadmapStore`, and its `_listing` reads each page through `get_github_session()` (`src/devops_cli/roadmap/stores/github_store.py`). So `resource://gh/issues/status` holds a GitHub session read of up to 60 s in a bound of 30 s.
- Source: `InProcessDispatcher` returns exit code 124 and `Command timed out after <timeout> seconds` when the command runs longer than its bound (`src/devops_cli/ai/mcp/dispatcher.py`).
- Source: `gh pages status` and `gh views audit` read GitHub through `run_gh` (`src/devops_cli/github/rate_limiter.py`), which waits up to 30 s for each attempt of `gh` and can try again. That is not shorter than the bound of 30 s either.
- Source: `gh project status` reads only the local project template (`@dry_run_class("no-external-request")`). It takes the same bound as the other `resource://gh/` resources (design).
- The premise is correct. The MCP tools of `CONST_MCP_EXPOSURE_TABLE` have the same problem: 23 `gh` tools and 11 `pr` tools have a bound of 60 s or less. The issue names the resources only, so #4784 holds the tools.

## Existing Tool Considered

The `timeout` argument of `_run_mcp_cmd` and of the MCP dispatcher, and the constant `DEFAULT_MCP_TOOL_TIMEOUT_SECONDS`, which exist. No new tool, no new constant and no new code path. Cost: about 20,000 tokens and 30 minutes to build, and no upkeep beyond the constants. The change deletes no internal code.
