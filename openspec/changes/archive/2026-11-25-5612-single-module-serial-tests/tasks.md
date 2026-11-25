# Tasks

## 1. Single-module serial worker selection

> Kind: behavior

- [x] 1.1 Update `tests/commands/test_test_selection.py` and `tests/commands/test_ci_repeat.py` with failing tests for single-module serial runs (`-n 0`, no `--collect-only`), multi-module count threshold (`51` collected tests across 2 modules), explicit `-n 2` override, and `-n` help text
  - Verification: `$ uv run devops ci test tests/commands/test_test_selection.py tests/commands/test_ci_repeat.py tests/commands/test_ci.py`
- [x] 1.2 Return `"0"` before collection when `len(targets) == 1` in `_narrowed_workers` (`src/devops_cli/commands/ci.py`) and update `HELP.ci.num_workers` (`src/devops_cli/lang/en/help.py`)
  - Verification: `$ uv run devops ci test tests/commands/test_test_selection.py tests/commands/test_ci_repeat.py tests/commands/test_ci.py`

## 2. Documentation

> Kind: documents

- [x] 2.1 Update `docs/TESTING.md` and run `uv run devops docs generate` to refresh `docs/commands/ci.md` and `docs/CLI_REFERENCE.md`
  - Verification: `$ uv run devops ci --check --no-cache --only docs`

Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
