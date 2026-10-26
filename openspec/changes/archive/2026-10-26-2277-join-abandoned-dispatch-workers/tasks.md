# Tasks

## 1. Failing test

- [x] Add a floor invariant test in `tests/invariants/test_hermetic_floor.py` proving that an abandoned dispatch worker is finished before the next test starts
  - Verification: `uv run devops ci test tests/invariants/test_hermetic_floor.py`

## 2. Fix

- [x] Add `CONST_MCP_DISPATCH_THREAD_NAME` to `src/devops_cli/config/constants.py` and name the worker thread in `src/devops_cli/ai/mcp/dispatcher.py`
  - Verification: `uv run devops ci test tests/test_fastmcp_in_process.py`
- [x] Add the `finish_abandoned_dispatch_workers` autouse fixture to `tests/conftest.py`
  - Verification: `uv run devops ci test tests/invariants/test_hermetic_floor.py tests/test_fastmcp_in_process.py`

## 3. Verification and static checks

- [x] Verify fail-to-pass check run passes against base
  - Verification: `uv run devops ci fail-to-pass --base origin/main`
- [x] Verify full static checks pass
  - Verification: `uv run devops ci`

## Workflow follow-up

- Pending a person: review the diff in tuicr (`tuicr -r origin/main..HEAD`).
