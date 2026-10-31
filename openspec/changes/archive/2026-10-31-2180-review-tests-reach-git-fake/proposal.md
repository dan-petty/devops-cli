# Proposal

## Why

Issue #2143 records the rule: a test of `src/` starts no program. The review tests still start a real `git` binary. An audit of the test suite recorded 114 tests across 15 files that start `git`:
- `tests/security/test_review_tool_runs.py` (43 tests)
- `tests/review/test_review_untrusted_tree.py` (21 tests)
- `tests/ai/review/test_review_path_routing.py` (7 tests)
- `tests/ai/review/test_review_project_conventions.py` (6 tests)
- `tests/git/test_review_worktree_regression.py` (5 tests)
- `tests/ai/review/test_review_samples.py` (5 tests)
- `tests/ai/review/test_review_sample_validation.py` (4 tests)
- `tests/review/test_review_group_analysis.py` (3 tests)
- `tests/ai/review/test_runner.py` (3 tests)
- `tests/ai/review/test_review_repos.py` (2 tests)
- `tests/commands/test_review_pre_analysis_only.py` (1 test)
- `tests/ai/review/test_review_security_tools.py` (1 test)
- `tests/ai/review/test_review_runner.py` (1 test)
- `tests/ai/review/test_review_path.py` (1 test)
- `tests/ai/review/test_review_backend_activity.py` (1 test)

Issue #2146 delivered the `git_fake` fixture. These tests must use `git_fake` and start no git process.

## What Changes

- Tests in the 15 files above reach `git` through `git_fake`.
- Test helpers and fixtures that start a real `git` to build repositories under `tmp_path` are replaced by file creation and scripted `git_fake` responses.
- Any start of a real `git` binary fails under `git_fake`.
- No test patches a `devops_cli` name.
- The pull request records the summed execution duration before and after the change.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `tests/security/test_review_tool_runs.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/review/test_review_untrusted_tree.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_review_path_routing.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_review_project_conventions.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/git/test_review_worktree_regression.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_review_samples.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_review_sample_validation.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/review/test_review_group_analysis.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_runner.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_review_repos.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/commands/test_review_pre_analysis_only.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_review_security_tools.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_review_runner.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_review_path.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/review/test_review_backend_activity.py`: Use `git_fake` and file fixtures instead of real git.

## Feasibility

Checked on 2026-10-31 against `tests/support/fakes/git.py` and the target test files:
- An audit of the 15 files with `sys.addaudithook` confirmed 114 tests starting `git` and a baseline duration of 77.20s across 248 tests.
- `git_fake` installs a `GitFake` instance into the process runner seam.
- `git_fake` intercepts `run_subprocess` calls for `git` and answers them through recorded scenarios or scripted `ProcessAnswer` records.
- When `git_fake` is active, `subprocess.Popen.__init__` checks the started program and fails if a real `git` binary starts.
- Code under test routes `git` calls through `devops_cli.core.process.run_subprocess` or reads files under `.git`.

## Existing Tool Considered

`git_fake` in `tests/support/fakes/git.py` provides the hermetic git fake seam. No new tool is needed.
