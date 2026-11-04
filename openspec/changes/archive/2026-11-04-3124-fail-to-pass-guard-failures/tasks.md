# Tasks

## 1. Allow the common git directory of a linked worktree (behavior)

Reads: `tests/conftest.py`, `src/devops_cli/core/repo.py`, `src/devops_cli/telemetry/tracer.py`. Changes: `tests/support/host_paths.py`, `tests/conftest.py`, `tests/invariants/test_host_path_roots.py`.

- [x] 1.1 Write the failing tests of the allowed roots: the `HEAD` file of a linked worktree opens, a file of the main checkout outside `.git` does not, a plain checkout and a submodule add no root, and the process fake records no call.
  - Verification: `uv run devops ci test tests/invariants/test_host_path_roots.py`
- [x] 1.2 Move the host path rules of `tests/conftest.py` to `tests/support/host_paths.py`. Add the common git directory from `_linked_worktree_common_dir`, and remove the main worktree path.
  - Verification: `uv run devops ci test tests/invariants/test_host_path_roots.py tests/invariants/test_hermetic_floor.py tests/invariants/test_test_module_independence.py`
- [x] 1.3 Replay a throwaway test that calls `_detect_vcs_metadata` and a changed `tests/ai/mcp/test_mcp.py` with `uv run devops ci fail-to-pass --base origin/main`, before and after the new root, and keep the result for the pull request comment.
  - Verification: `uv run devops ci fail-to-pass --base origin/main --dry-run`

## 2. Refuse a replay that proves nothing (behavior)

Reads: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/git/operations.py`, `tests/ci/test_fail_to_pass.py`. Changes: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/ci/changed_tests.py`, `src/devops_cli/git/operations.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/ci/test_fail_to_pass.py`, `tests/ci/test_changed_tests.py`, `tests/invariants/test_hermetic_floor.py`.

- [x] 2.1 Write the failing tests: a host path guard message in a failure or in a teardown error, an edge guard message that keeps the replay satisfied, the roots of `allowed_host_roots`, an unchanged test that fails, a parametrized test, a changed helper, and a new test that fails in full, and the cases of the function comparison.
  - Verification: `uv run devops ci test tests/ci/test_fail_to_pass.py tests/ci/test_changed_tests.py`
- [x] 2.2 Add `CONST_FAIL_TO_PASS_HOST_PATH_GUARD_MESSAGE`, the two report sentences, `changed_tests.is_test_changed`, `unchanged_failed` and `host_path_guard_failures` on the report, the rule in `satisfied`, and the two git reads in the dry run plan.
  - Verification: `uv run devops ci test tests/ci/test_fail_to_pass.py tests/ci/test_changed_tests.py tests/git/test_git_operations.py`

## 3. Documents (documents)

Changes: `CONTRIBUTING.md`, `docs/TESTING.md`.

- [x] 3.1 Describe the new rules of the check in `CONTRIBUTING.md` and the host path roots in `docs/TESTING.md`.
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
