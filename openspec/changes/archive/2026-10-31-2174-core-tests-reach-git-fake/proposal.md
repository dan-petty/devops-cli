# Proposal

## Why

Issue #2143 records the rule: a test of `src/` starts no program. The data directory, run store and gitignore tests still start a real `git`. An audit of the test suite recorded 142 tests across four files that start `git`:
- `tests/core/test_data_dir_worktrees.py` (88 tests)
- `tests/core/test_gitignore_evaluation.py` (22 tests)
- `tests/ai/test_run_store.py` (18 tests)
- `tests/ai/test_run_comparison.py` (14 tests)

Issue #2146 delivered the `git_fake` fixture. These tests must use `git_fake` so they start no program.

## What Changes

- Tests in `tests/core/test_data_dir_worktrees.py`, `tests/core/test_gitignore_evaluation.py`, `tests/ai/test_run_store.py`, and `tests/ai/test_run_comparison.py` reach `git` through `git_fake`.
- Test helpers that start a real `git` to build repositories under `tmp_path` are removed. The test writes files directly to the file system and states `git` answers or replays recorded transcripts.
- Any start of a real `git` fails under `git_fake`.
- No test patches a `devops_cli` name.
- The pull request records the summed execution duration before and after the change.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `tests/core/test_data_dir_worktrees.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/core/test_gitignore_evaluation.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/test_run_store.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ai/test_run_comparison.py`: Use `git_fake` and file fixtures instead of real git.

## Feasibility

Checked on 2026-10-31 against `tests/support/fakes/git.py` and the target test files:
- `git_fake` installs a `GitFake` instance into the process runner seam.
- `git_fake` intercepts `run_subprocess` calls for `git` and answers them through recorded scenarios or scripted `ProcessAnswer` records.
- When `git_fake` is active, `subprocess.Popen.__init__` checks the started program and fails if a real `git` binary starts.
- Code under test routes `git` calls through `devops_cli.core.process.run_subprocess` or uses files under `.git`.

## Existing Tool Considered

`git_fake` in `tests/support/fakes/git.py` provides the hermetic git fake seam. No new tool is needed.
