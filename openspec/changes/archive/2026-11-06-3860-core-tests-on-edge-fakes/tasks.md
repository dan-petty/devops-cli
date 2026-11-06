# Tasks

## 1. The retry interval of a failed GitHub lookup follows the clock seam (behavior)

- [x] 1.1 Test: `test_git_waits_before_looking_again_after_a_failed_lookup` moves the time with the `clock` fixture and expects git to look for the token again after the interval (it fails on the base)
  - Verification: `uv run devops ci test tests/core/test_subprocess_env_boundary.py`
- [x] 1.2 `_session_github_token` in `src/devops_cli/core/process.py` reads `clock.monotonic()` in place of `time.monotonic()`
  - Verification: `uv run devops ci test tests/core/test_subprocess_env_boundary.py`

## 2. The tests of the JSON runner use the process fake (test-only edits)

- [x] 2.1 Move `tests/core/test_consolidation_process_json.py` to `process_fake`, and check that the input and the working directory reach the child
  - Verification: `uv run devops ci test tests/core/test_consolidation_process_json.py`
- [x] 2.2 No test of `core` patches `run_subprocess`
  - Verification: `! git grep -n -F -e "core.process.run_subprocess" -- tests/core`

## 3. The tests of the GitHub identity use no private name (test-only edits)

- [x] 3.1 Move the tests of `tests/core/test_subprocess_env_boundary.py` to `reset_github_token`, to the token of `pin_github_session`, to the `clock` fixture and to `process_fake`, and name `reset_github_token` in the docstring of `pin_github_session`
  - Verification: `uv run devops ci test tests/core/test_subprocess_env_boundary.py tests/config/test_isolation_tripwire.py`
- [x] 3.2 No test of `core` assigns or reads a private name of the GitHub identity
  - Verification: `! git grep -n -F -e "process._github" -e "_github_lookup_failure" -- tests/core`

## 4. Archive

- [x] 4.1 Archive the change
  - Verification: `uv run devops openspec archive 3860-core-tests-on-edge-fakes`

## Workflow follow-up

- The other items of #1333 move the tests of config, git, dry-run and root modules, http, and exceptions, lang and models, remove the accommodations, and delete dead code. The private imports and internal patches of the other core test files (`test_audit_stream.py`, `test_coverage_index.py`, `test_data_dir_worktrees.py`, `test_template_rendering.py`, `test_validation.py`, `test_process.py`) belong to those items and to the reorganization item of #1333.
