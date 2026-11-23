# Tasks

## 1. Mutants Tree Preparation

- [x] 1.1 Add `prepare_mutants_tree` in `src/devops_cli/ci/mutate.py`
  - Verification: `$ uv run pytest tests/ci/test_ci_mutate.py -k test_mutants_root_preparation`
- [x] 1.2 Call `prepare_mutants_tree` in `devops ci mutate` in `src/devops_cli/commands/ci.py`
  - Verification: `$ uv run pytest tests/ci/test_ci_mutate.py -k test_mutate_runs_mutmut`
- [x] 1.3 Add tests for nearest Git directory and repository resolution in mutants tree
  - Verification: `$ uv run pytest tests/ci/test_ci_mutate.py`

## 2. Quality Gate

- [x] 2.1 Validate OpenSpec artifacts
  - Verification: `$ uv run devops openspec check`
