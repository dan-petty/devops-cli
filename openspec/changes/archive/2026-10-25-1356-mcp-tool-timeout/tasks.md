# Tasks

## 1. Failing tests

- [x] Add failing test cases for in-process command timeout in `tests/test_fastmcp_in_process.py`
  - Verification: `uv run devops ci test tests/test_fastmcp_in_process.py`

## 2. In-process dispatcher timeout implementation

- [x] Update `dispatch`, `_dispatch_typer`, and `_dispatch_subprocess` in `src/devops_cli/ai/mcp/dispatcher.py` to enforce deadlines
  - Verification: `uv run devops ci test tests/test_fastmcp_in_process.py`
- [x] Regenerate documentation
  - Verification: `uv run devops docs generate --sync-readme`

## 3. Static checks and OpenSpec validation

- [x] Verify fast checks and OpenSpec gate pass
  - Verification: `uv run devops openspec check`
  - Verification: `uv run devops ci`
