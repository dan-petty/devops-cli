# Tasks

## 1. Behavior

- [x] 1.1 Eliminate internal string patches in remaining command test files
  - Verification: `$ uv run python -c "from tests.invariants.test_source_tree import _string_patches_of_devops_cli; from pathlib import Path; assert all(not _string_patches_of_devops_cli(p.read_text()) for p in Path('tests/commands').rglob('*.py'))"`
- [x] 1.2 Update invariant check in `tests/invariants/test_source_tree.py`
  - Verification: `$ uv run pytest tests/invariants/test_source_tree.py`
- [x] 1.3 Verify all tests in `tests/commands/` pass
  - Verification: `$ uv run pytest tests/commands/`

## 2. Documents

- [x] 2.1 Update OpenSpec proposal and archive change
  - Verification: `$ uv run devops openspec archive 3769-command-tests-patch-no-devops-cli`
