# Proposal

## Why

Issue #3760 is a child of #1330 (tracker: MCP tool tests use fakes at the edges) and of #1307. The MCP tool tests patch `_run_mcp_cmd` and `run_subprocess` by string name. Both patches name internals of devops-cli. The process fake cannot replace them. An MCP tool passes a `uv run devops` command line to `InProcessDispatcher`, and the dispatcher runs the Typer app in the same process. No process starts, so the process fake never sees the command line.

The subprocess branch of `_run_mcp_cmd` and `InProcessDispatcher._dispatch_subprocess` could run only when a command line was not a `devops` one. Every call in `src` passes a `devops` command line. So these branches ran only in tests.

## What Changes

- Add `McpDispatcher` (a `Protocol`) and `install_mcp_dispatcher(dispatcher)` in `src/devops_cli/ai/mcp/dispatcher.py`. `get_mcp_dispatcher()` returns the installed dispatcher. The public `reset_mcp_dispatcher()` removes it. The reset hook of the test floor (`tests/conftest.py`) already calls `reset_mcp_dispatcher` after each test.
- Delete the subprocess branch of `_run_mcp_cmd` in `ai/mcp/server.py` and `InProcessDispatcher._dispatch_subprocess`. `ai/mcp/dispatcher.py` and `ai/mcp/server.py` import no `subprocess` and no `run_subprocess`.
- A command line that is not a `devops` one now raises `ValidationError` (message `ERRORS.mcp.not_a_devops_command`). Nothing runs. The public `devops_sub_args(cmd)` replaces the private `_extract_devops_sub_args`.
- Add `DispatcherFake` in `tests/support/fakes/mcp_dispatcher.py` behind the `mcp_dispatcher` fixture. It records each call and answers by command prefix. A contract suite, `tests/ai/mcp/test_dispatcher_contract.py`, runs the same cases against the fake and against `InProcessDispatcher`.
- Move the tests of `test_fastmcp_in_process.py`, `test_mcp.py` and `test_fastmcp_contracts.py` that patched `_run_mcp_cmd`, `run_subprocess` or `InProcessDispatcher._dispatch_typer` to the `mcp_dispatcher` fixture. Tests of `_validate_mcp_arg` go through a public tool.
- Correct `docs/TESTING.md` (a faked process edge "`uv run devops` calling itself" does not exist; add the dispatcher seam) and the FastMCP page of the knowledge base (tools no longer run a subprocess).
- This change alters no behaviour a consumer observes: every tool already passed only `devops` command lines. So it sets `skip_specs: true`.
- Not in this change: the patches of `devops_cli.ai.mcp.server.mcp`, `devops_cli.commands.mcp.run_mcp_server`, `mcp._list_tools`, `schema_violations` and `main._delegate`, the `PropertyMock` of `mcp.instructions`, the patches of `_run_mcp_cmd` in other test files, and the file split (child F of #1330). They stay with their own items.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `src/devops_cli/ai/mcp/dispatcher.py`, `src/devops_cli/ai/mcp/server.py`, `src/devops_cli/lang/en/errors.py` (one message).
- `tests/support/fakes/mcp_dispatcher.py`, `tests/ai/mcp/` (four files), `docs/TESTING.md`, `src/devops_cli/ai/knowledge_base/devops_cli/libraries/fastmcp.md`.

## Feasibility

Checked on the tree at origin/main (c7145511):
- `git grep -n "_run_mcp_cmd" -- src` shows the callers in `ai/mcp/server.py` and one in `ai/mcp/generator.py`. Each passes `["uv", "run", "devops", ...]`.
- `InProcessDispatcher._dispatch_typer` runs the Typer app with `CliRunner` in the same process and never calls `run_subprocess`.
- `git grep -n "assert_called" -- src` returns no line. The mock check named in the issue (`hasattr(run_subprocess, "assert_called")`) is not in the tree, so there is nothing more to remove for it.
- `tests/conftest.py` lists `devops_cli.ai.mcp.dispatcher: reset_mcp_dispatcher` in its reset table. The invariant test for that table passes with the new hook.

## Existing Tool Considered

No open tool fakes the in-process dispatch of devops-cli. FastMCP `Client(mcp)` (in-memory transport) is the open tool for a client call, and the tests use it. Typer `CliRunner` is the real side of the contract suite. The process fake does not apply: no process starts. The own code is the hook (about 15 lines), `DispatcherFake` (about 130 lines) and its contract suite. Cost to build: about 35,000 tokens. Cost to keep and fix: about 8,000 tokens a year. Elapsed time: half a day. Without it, 20 patches of an internal name stay and no test can read the command line of a tool.
