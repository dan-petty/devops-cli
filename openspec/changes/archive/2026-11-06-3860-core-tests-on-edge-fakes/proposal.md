# Proposal

## Why

Issue #3860 is item 1 of the Fit note of #1333, which is a part of #1307. The tests of `src/devops_cli/core/process.py` still reach the private state of the runner. The tests of the JSON runner patch the runner function. ADR 0007 and `docs/TESTING.md` say that a test patches no `devops_cli` name and imports no private name. The process fake (`process_fake`) and the pinned GitHub identity of the floor already exist, but these tests do not use them.

## What Changes

- `tests/core/test_consolidation_process_json.py` answers the child through `process_fake`. It does not patch `devops_cli.core.process.run_subprocess` 6 times any more. It also checks that the input and the working directory reach the child.
- `tests/core/test_subprocess_env_boundary.py` assigns and reads no private name of `core/process.py`:
  - A test that needs no identity calls `reset_github_token()`.
  - A test that needs a token reads the one that `pin_github_session` yields, in place of the string `"A"` that it assigned to `_github_token`.
  - The test of the retry interval of a failed lookup moves the clock with the `clock` fixture, in place of the assignment of `_github_lookup_failure`.
  - The test of the unauthenticated error answers `gh auth token` through `process_fake`.
  - The tests that check the environment of a child keep the double of the stdlib `subprocess.run`. They test `DefaultProcessRunner`, which is the real implementation of the process seam, and `docs/TESTING.md` allows the double of a stdlib edge.
- `src/devops_cli/core/process.py` reads `clock.monotonic()` of the clock seam (#1320) in `_session_github_token`, in place of `time.monotonic()`. This is the only way for a test to move the time of the retry interval without a private assignment. The behavior does not change.
- `tests/conftest.py`: the docstring of `pin_github_session` names `reset_github_token`, in place of the private assignment that it named before.
- Not changed: `tests/support/github_identity.py` and the `pin_github_session` fixture itself (the accommodations item of #1333), the `PYTEST_CURRENT_TEST` pass-through and the async reroute of `core/process.py`, and the private imports and internal patches of the other core test files that are not about the process or the GitHub token.
- This change alters no behavior a consumer observes: no command, option, message or request changes. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request.

## Impact

- `src/devops_cli/core/process.py` (one import, two clock reads).
- `tests/core/test_consolidation_process_json.py`, `tests/core/test_subprocess_env_boundary.py` and `tests/conftest.py` (one docstring).

## Feasibility

Checked on `origin/main` 5bc50d0a, 2026-11-06. The premise of item 1 holds in a smaller form. The tree has moved since #1333 was written, so each claim was counted again.

- `git grep -n -F -e "core.process.run_subprocess" -- tests/core` found 6 patches, all in `tests/core/test_consolidation_process_json.py`. The "20" of #1333 counted 12 more in `git/operations` tests, which are item 3, and the others are gone.
- `process._github_token` is assigned 5 times, and `process._github_lookup_failure` is read and assigned once, all in `tests/core/test_subprocess_env_boundary.py`. The other 14 files that #1333 names for `core` hold no such site. `test_command_decorator.py`, `test_consolidation_cli_errors.py` and `test_process_pipeline.py` no longer exist.
- `process_fake` replaces the whole runner, so it skips the pin of the GitHub token and the build of the child environment, which `DefaultProcessRunner.run` does. So the tests of the pin and of the child environment cannot run on `process_fake`. They run on the real runner over the stdlib `subprocess.run` double. The tests of `github_token()` and of `run_json_subprocess` do not need the real runner, and they run on `process_fake`.
- `reset_github_token()` is public and sets all three private values to `None`. `pin_github_session` (the autouse fixture of the floor) yields the token that it pins. So no test needs to assign a private name.
- The retry interval used `time.monotonic()`, which no fixture moves. The `clock` fixture moves the monotonic reading of the clock seam (`devops_cli.core.clock`), and the seam is already the way for the other modules to read a monotonic time (`ci/gate_slots.py`, `github/pr_monitor.py`, `security/vulnerability_lookup.py`). The new test `test_git_waits_before_looking_again_after_a_failed_lookup` failed on the base for that reason: git did not look again after the interval, because the fake clock did not move `time.monotonic()`.
- Mutation check: a change of the product code makes the migrated tests fail. Four changes were tried in `core/process.py` on a scratch edit: the check of `run_json_subprocess` turned around (2 tests failed), the exit code 127 reason removed (1 failed), the retry interval removed (1 failed), and the retry interval made endless (1 failed).

## Existing Tool Considered

Not applicable: this change builds nothing. It uses pytest, `time-machine` through the `clock` fixture, and the shared `process_fake`. It deletes no internal code of its own. It removes 6 patches of `run_subprocess`, 5 assignments of `_github_token` and the read and assignment of `_github_lookup_failure` from the tests.
