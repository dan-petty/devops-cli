# Proposal

## Why

Issue #2143 records the rule: a test of `src/` starts no program. The `devops ci`, `devops test` and `fail-to-pass` tests still start a real `git`. An audit of the test suite recorded 93 tests across eight files that start `git`:
- `tests/commands/test_ci.py` (18 tests)
- `tests/ci/test_fail_to_pass.py` (21 tests)
- `tests/commands/test_test_runner.py` (17 tests)
- `tests/ci/test_ci_cache_fingerprint.py` (16 tests)
- `tests/ci/test_ci_mutate.py` (11 tests)
- `tests/ci/test_ci_cache.py` (6 tests)
- `tests/commands/test_ci_build_index.py` (3 tests)
- `tests/commands/test_uv.py` (1 test)

Issue #2146 delivered the `git_fake` fixture. These tests must use `git_fake` so they start no program.

## What Changes

- Tests in the eight files above reach `git` through `git_fake`.
- Test helpers that start a real `git` to build repositories under `tmp_path` are replaced by file creation and scripted `git_fake` responses.
- Any start of a real `git` binary fails under `git_fake`.
- No test patches a `devops_cli` name.
- The pull request records the summed execution duration before and after the change.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- `tests/commands/test_ci.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ci/test_fail_to_pass.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/commands/test_test_runner.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ci/test_ci_cache_fingerprint.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ci/test_ci_mutate.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/ci/test_ci_cache.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/commands/test_ci_build_index.py`: Use `git_fake` and file fixtures instead of real git.
- `tests/commands/test_uv.py`: Use `git_fake` and file fixtures instead of real git.

## Feasibility

Checked on 2026-10-31 against `tests/support/fakes/git.py` and the target test files:
- `git_fake` installs a `GitFake` instance into the process runner seam.
- `git_fake` intercepts `run_subprocess` calls for `git` and answers them through recorded scenarios or scripted `ProcessAnswer` records.
- When `git_fake` is active, `subprocess.Popen.__init__` checks the started program and fails if a real `git` binary starts.
- Code under test routes `git` calls through `devops_cli.core.process.run_subprocess` or uses files under `.git`.

## Existing Tool Considered

`git_fake` in `tests/support/fakes/git.py` provides the hermetic git fake seam. No new tool is needed.
