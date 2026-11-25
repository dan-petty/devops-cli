## Problem
This is a Copilot thread on release PR #1283, verified at b57ef7f. MCP tools pass a `timeout` to `_run_mcp_cmd`; `ci_run`, for example, uses the CI test budget plus its margin [code: src/devops_cli/ai/mcp/server.py:676]. A `uv run devops ...` command is routed to `InProcessDispatcher.dispatch`, which runs it in-process through `_dispatch_typer` and never applies the timeout [code: src/devops_cli/ai/mcp/dispatcher.py:291-335]. A hung in-process command therefore blocks the tool indefinitely. The same path exists on `main` (v0.2.27), so it predates this release.

## Acceptance criteria
- [ ] Every MCP tool stops at its timeout. A command that must be bounded runs where it can be stopped, such as a subprocess through the process runner, or an in-process run with an enforced deadline that returns a timeout error naming the tool.
- [ ] A test with a command that never returns shows the tool returning a timeout error within its budget.
- [ ] `uv run devops ci` passes.

## Strategic alignment
- **Related:** #839, #775 (one process runner), #1283.
