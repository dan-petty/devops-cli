# Tasks

## 1. Remove Module-Level Live Marks and Mark Individual Tests

- [x] Update `tests/commands/test_cli_startup_imports.py`
  - Remove module-level `pytestmark = pytest.mark.live("python")`
  - Add `@pytest.mark.live("python")` only to test functions that execute python subprocesses
  - Verification: `uv run pytest tests/commands/test_cli_startup_imports.py`
- [x] Update `tests/config/test_isolation_tripwire.py`
  - Remove module-level `pytestmark = pytest.mark.live("python")`
  - Add `@pytest.mark.live("python")` only to test functions that execute python subprocesses
  - Verification: `uv run pytest tests/config/test_isolation_tripwire.py`
- [x] Update `tests/core/test_subprocess_env_boundary.py`
  - Remove module-level `pytestmark = pytest.mark.live("python")`
  - Add `@pytest.mark.live("python")` only to test functions that execute python subprocesses
  - Verification: `uv run pytest tests/core/test_subprocess_env_boundary.py`
- [x] Update `tests/core/test_process.py`
  - Remove module-level `pytestmark` list with live markers
  - Add `@pytest.mark.live(...)` with specific programs to test functions that execute them
  - Verification: `uv run pytest tests/core/test_process.py`
- [x] Update `tests/commands/test_ci.py`
  - Remove module-level `pytestmark` list with live markers
  - Add `@pytest.mark.live(...)` with specific programs to test functions that execute them
  - Verification: `uv run pytest tests/commands/test_ci.py`

## 2. Verify Floor Enforcement and CI Gates

- [x] Confirm no module sets `live` in `pytestmark`
  - Verification: `grep -rn "pytestmark.*live" tests/commands/test_ci.py tests/core/test_process.py tests/core/test_subprocess_env_boundary.py tests/config/test_isolation_tripwire.py tests/commands/test_cli_startup_imports.py` returns 0 matches
- [x] Confirm a test that executes an unlisted binary fails at the hermetic floor on a scratch test
  - Verification: Scratch test execution fails with hermetic floor violation
- [x] Pass all quality gates
  - Verification: `uv run devops ci`
