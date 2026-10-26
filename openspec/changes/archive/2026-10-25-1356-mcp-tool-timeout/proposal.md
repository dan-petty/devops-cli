# Proposal

## Why

Issue #1356: An MCP tool stops at its timeout, also when its command runs in-process.
MCP tools pass a `timeout` argument to `_run_mcp_cmd`.
Commands that begin with `uv run devops` or `devops` route to `InProcessDispatcher.dispatch`.
The dispatcher invokes `_dispatch_typer` without the `timeout` parameter.
Typer executes the command synchronously via `CliRunner.invoke`.
A hung command blocks the in-process execution indefinitely.

## What Changes

- `InProcessDispatcher.dispatch` forwards `timeout` to `_dispatch_typer`.
- `_dispatch_typer` runs the command invocation in a worker thread bounded by the deadline.
- When the execution exceeds the timeout, the dispatcher returns exit code 124 with a message that names the command.
- The command stdio redirection and Python standard streams are restored on timeout.
- This change alters observable behavior for MCP clients that execute long-running or hung commands.
- The change defines the `mcp-tool-timeout` capability spec.
- This change fits in one pull request.

## Capabilities

### New Capabilities

- `mcp-tool-timeout`: Enforce execution deadlines across in-process and external MCP tool invocations.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/mcp/dispatcher.py` (`dispatch`, `_dispatch_typer`, `_dispatch_subprocess`).
- Tests: `tests/test_fastmcp_in_process.py`.
- Documentation: `src/devops_cli/ai/knowledge_base/devops_cli/libraries/fastmcp.md`.

## Feasibility

- Premise confirmed at commit 4776f632 (`origin/main`).
- `src/devops_cli/ai/mcp/dispatcher.py:285-300` defines `dispatch(cmd, timeout=...)`.
- Line 296 executes `code, out = self._dispatch_typer(sub_args, env=env)`.
- Line 301 defines `_dispatch_typer(self, sub_args, env=None)` with no timeout parameter.
- Typer's `CliRunner.invoke` executes commands synchronously on the current thread.
- Standard library `threading.Thread` with `join(timeout=timeout)` bounds synchronous execution offline.
- The change fits in `src/devops_cli/ai/mcp/dispatcher.py`.

## Existing Tool Considered

Standard library `threading.Thread` and `concurrent.futures` provide execution management.
FastMCP and Typer provide the MCP tool and CLI interfaces.
No new third-party dependency is required.
No internal code is deleted.
