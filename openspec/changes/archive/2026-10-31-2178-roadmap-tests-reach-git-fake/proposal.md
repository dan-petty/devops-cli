# Proposal

## Why

Issue #2143 records the rule: a test of `src/` starts no program. The roadmap refine, run and intake tests still start a real `git`. An audit of the test suite recorded 76 tests across three files that start `git`:
- `tests/roadmap/test_roadmap_refine.py` (59 tests)
- `tests/roadmap/test_roadmap_run.py` (10 tests)
- `tests/roadmap/test_roadmap_intake.py` (7 tests)

Issue #2146 delivered the `git_fake` fixture. These tests must use `git_fake` so they start no program.

## What Changes

- Tests in `tests/roadmap/test_roadmap_refine.py`, `tests/roadmap/test_roadmap_run.py`, and `tests/roadmap/test_roadmap_intake.py` reach `git` through `git_fake`.
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

- `tests/roadmap/test_roadmap_refine.py`: Remove `_git_run` and use `git_fake` for `git` commands.
- `tests/roadmap/test_roadmap_run.py`: Replace real `git` calls with `git_fake`.
- `tests/roadmap/test_roadmap_intake.py`: Replace real `git` calls with `git_fake`.

## Feasibility

Checked on 2026-10-31 against `tests/support/fakes/git.py` and the roadmap test files:
- `git_fake` installs a `GitFake` instance into the process runner seam.
- `git_fake` intercepts `run_subprocess` calls for `git` and answers them through recorded scenarios or scripted `ProcessAnswer` records.
- When `git_fake` is active, `subprocess.Popen.__init__` checks the started program and fails if a real `git` binary starts.
- The roadmap refine and run code routes all `git` calls through `devops_cli.core.process.run_subprocess`.

## Existing Tool Considered

`git_fake` in `tests/support/fakes/git.py` provides the hermetic git fake seam. No new tool is needed.
