# Tasks

## 1. Behavior

- [x] 1.1 Add shared `git_repo` fixture with recorded commit in `tests/support/git_repo.py`
  - Verification: `$ uv run devops ci test tests/git/test_git_repo_fixture.py`
- [x] 1.2 Add `tests/git/test_git_repo_fixture.py` verifying `git_repo` answers `HEAD` without real Git
  - Verification: `$ uv run devops ci test tests/git/test_git_repo_fixture.py`
- [x] 1.3 Add exclusions with reason comments to `pytest_add_cli_args_test_selection` in `pyproject.toml`
  - Verification: `$ uv run pytest tests/ci/test_ci_mutate.py`

## 2. Documents

- [x] 2.1 Document change proposal and design in OpenSpec change folder
  - Verification: `$ uv run devops openspec check`
