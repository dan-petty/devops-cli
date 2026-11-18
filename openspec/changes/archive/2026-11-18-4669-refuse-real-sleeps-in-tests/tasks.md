# Tasks

## 1. Refuse real sleeps in tests and static analysis

- [x] 1.1 Configure ruff TID251 banned-api in `pyproject.toml` to ban `time.sleep` without per-file ignores.
  - Verification: `$ uv run ruff check src/`
- [x] 1.2 Route all direct `time.sleep` calls in `src` through `devops_cli.core.clock.sleep`.
  - Verification: `$ uv run ruff check src/`
- [x] 1.3 Add `# noqa: TID251` to `src/devops_cli/core/clock.py` and set ceiling to 1 in `DEFAULT_SUPPRESSION_CEILINGS`.
  - Verification: `$ uv run pytest tests/invariants/test_architectural_invariants.py`
- [x] 1.4 Declare `real_sleep` marker in `pyproject.toml`.
  - Verification: `$ uv run pytest --markers`
- [x] 1.5 Implement PEP 578 audit hook and autouse fixture in `tests/conftest.py` with 0.25 s budget.
  - Verification: `$ uv run pytest tests/invariants/test_refuse_real_sleeps.py`
- [x] 1.6 Update tests in `tests/commands/test_pr_update.py` to use `clock: ClockFake`.
  - Verification: `$ uv run pytest tests/commands/test_pr_update.py`
- [x] 1.7 Add `@pytest.mark.real_sleep` to child process wait tests.
  - Verification: `$ uv run pytest tests/commands/test_ci.py -k "signal or sigterm"`
- [x] 1.8 Write floor invariant tests in `tests/invariants/test_refuse_real_sleeps.py`.
  - Verification: `$ uv run pytest tests/invariants/test_refuse_real_sleeps.py`
