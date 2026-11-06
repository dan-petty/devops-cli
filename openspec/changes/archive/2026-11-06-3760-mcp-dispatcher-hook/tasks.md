# Tasks

## 1. Product code
- [x] 1.1 Add `McpDispatcher`, `install_mcp_dispatcher` and `devops_sub_args` in `ai/mcp/dispatcher.py`; delete `_dispatch_subprocess`; verify with `git grep -nE 'run_subprocess|import subprocess' -- src/devops_cli/ai/mcp` (no line)
- [x] 1.2 Delete the subprocess branch of `_run_mcp_cmd` in `ai/mcp/server.py` and add the `not_a_devops_command` message; verify with `uv run pytest tests/ai/mcp/test_dispatcher_contract.py`

## 2. Fake and contract suite
- [x] 2.1 Add `DispatcherFake` and the `mcp_dispatcher` fixture in `tests/support/fakes/mcp_dispatcher.py`
- [x] 2.2 Add `tests/ai/mcp/test_dispatcher_contract.py` and run each case on the fake and on `InProcessDispatcher`; verify with `uv run pytest tests/ai/mcp/test_dispatcher_contract.py`

## 3. Test migration
- [x] 3.1 Move `test_fastmcp_in_process.py`, `test_mcp.py` and `test_fastmcp_contracts.py` off `_run_mcp_cmd`, `run_subprocess` and `_dispatch_typer` patches; verify with `git grep -nE '_run_mcp_cmd|run_subprocess' -- tests/ai/mcp/test_mcp.py tests/ai/mcp/test_fastmcp_contracts.py tests/ai/mcp/test_fastmcp_in_process.py` (no line)

## 4. Documents
- [x] 4.1 Correct `docs/TESTING.md` and the FastMCP knowledge-base page

## 5. Verification
- [x] 5.1 Run `uv run devops openspec check`, the static checks and `uv run devops ci`
