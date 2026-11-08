# Proposal

## Why

Issue #4087 is group 3 of #3769, which is part of #1307. The tests of `devops ci` and of its test selection still patch names inside `devops_cli`. #1336 turns the ratchets of #1309 into bans, and it fails on these patches.

At origin/main a224adbb, the eight test files of the group hold 134 patches of a `devops_cli` name, counted from the syntax tree of each file: 106 name a `devops_cli` module in a string (45 in `test_ci.py`, 11 in `test_ci_build_index.py`, 2 in `test_ci_dry_run.py`, 48 in `test_test_selection.py`), and 28 patch an attribute of the imported `ci` module (23 in `test_ci.py`, 5 in `test_ci_shard.py`). The files `test_ci_gate_rows.py`, `test_ci_maintain.py` and `test_ci_repeat.py` hold none.

Product code holds accommodations for these tests:

- `commands/ci.py` reads `PYTEST_CURRENT_TEST` twice in `_clean_coverage_artifacts`. The reads stop a test of the gate from deleting the `.coverage.*` files of the run that tests it. #4021 left them for this item.
- `commands/ci.py` holds `_current_run_subprocess` and `_ORIG_RUN_SUBPROCESS`, which let a test replace `run_subprocess` on the module.
- `_clean_coverage_artifacts(force=True)` and `_run_all_checks` have no caller in `src/`. Only tests call them.

The change folder `1325-ci-commands-edge-fakes` plans this work, but its parent #1325 is closed. It plans moves that this item does not make, and it names commands that belong to the other groups of #3769.

## What Changes

- The tests that start the gate run in a root of their own. `tests/support/ci_root.py` holds the `ci_root` fixture (an empty work tree under `tmp_path`, the current directory), the `ci_head` fixture (git answers `rev-parse HEAD`) and `tracked_blobs` (git lists a given set of files). The gate then cleans and caches only in that root.
- Each patch of a `devops_cli` name goes. The `process_fake` and `git_fake` fixtures answer the programs, the `clock` fixture moves the time of a check, the real cache functions of `devops_cli.ci.cache` hold the verdict, and the tests read the output of the command. The count of such patches in the group goes from 134 to 0.
- The tests of `tests/ci/test_ci_gate_admission.py` that run a check through the gate use `ci_root` too.
- Four test names that named a private function change: `test_execute_check_async_success_and_failure` is now `test_a_check_passes_when_its_command_exits_zero_and_fails_when_it_does_not`, `test_execute_check_async_timeout_expired` is `test_a_check_that_times_out_fails_and_says_so`, `test_try_save_ci_cache_and_handle_results` is `test_a_passing_gate_records_its_verdict_and_a_failing_gate_clears_it`, and the invariant `test_product_code_reads_pytest_current_test_no_more_than_its_ceiling` is `test_product_code_never_reads_pytest_current_test`. Every other test id stays. One test is new: `test_the_coverage_clean_up_keeps_the_files_of_a_live_worker_and_a_fresh_file`. The guards of `_clean_coverage_artifacts` that the old check hid have a test of their own now.
- Source: the two reads of `PYTEST_CURRENT_TEST`, `_current_run_subprocess`, `_ORIG_RUN_SUBPROCESS`, the `force` argument of `_clean_coverage_artifacts` and `_run_all_checks` are deleted. `_execute_check_async` times a check with the clock seam (`core/clock.py`), as the rest of the command does, so a test can move the time. `gate_root_warnings` in `ci/diagnostics.py` holds the two warnings about the checked tree. `directory_modules` and `shard_test_files` move from `commands/ci.py` to `core/test_selection.py` as public functions.
- `tests/invariants/test_source_tree.py` bans every read of `PYTEST_CURRENT_TEST` in `src/` (its ceiling was 2), and `docs/TESTING.md` says so.
- The stale change folder `openspec/changes/1325-ci-commands-edge-fakes` is removed. #3769 and its children carry the work.
- This change alters no behavior a consumer observes: the commands, their options and messages are the same. It has no spec delta, and `skip_specs: true` is set.
- This change fits one pull request.
- Not in this change: `tests/commands/test_test_runner.py` (the `devops test` command, group 4 of #3769); the two tests of `test_ci.py` that call `_session_returncode` and `_cancelled_by_stop_signals`, which stay until the stop-signal code moves to `core/process.py`; the workflow invariant tests inside `test_ci.py`; and a ratchet on the patches of the command tests, which #1336 owns. No ratchet that counts these patches exists in `tests/invariants` today, so no ceiling goes down here beyond the one for `PYTEST_CURRENT_TEST`.

## Impact

- `src/devops_cli/commands/ci.py`, `src/devops_cli/core/test_selection.py`, `src/devops_cli/ci/diagnostics.py`.
- `tests/support/ci_root.py` (new), `tests/commands/test_ci.py`, `test_ci_build_index.py`, `test_ci_dry_run.py`, `test_ci_shard.py`, `test_test_selection.py`, `tests/ci/test_ci_gate_admission.py`, `tests/invariants/test_source_tree.py`.
- `docs/TESTING.md`.
- `openspec/changes/1325-ci-commands-edge-fakes` (removed).

## Feasibility

Checked on origin/main a224adbb, 2026-11-07.

- The premise of #3769 holds for this group. `git grep` and the syntax-tree count above find 134 patches in five of the eight files.
- The `devops ci` tests can run in a root of their own with the process fake. `find_worktree_root` resolves the root from the current directory, and a directory with a `.git` entry under `tmp_path` is a root (`core/repo.py`). `ProcessFake.run` and `ProcessFake.run_async` answer every program of the gate, so `run_subprocess` and `run_subprocess_async` need no patch. `tests/commands/test_ci_repeat.py` already ran this way.
- The root needs the fixture. An old `.coverage.sample` file was put in the repository root and in its `.data/` before each test, and the guard was removed from `_clean_coverage_artifacts`. Seven tests that start the gate in the repository root deleted both files: four in `test_ci.py` and three in `tests/ci/test_ci_gate_admission.py`. With `ci_root` on those tests, no test of the three directories deleted a file.
- The `_clean_coverage_artifacts` guard against a live worker still stands without the test check: a file with the pid of a live process, and a file younger than one minute, stay. The tests age their files and name a pid above the highest one Linux gives, so no live worker holds the name.
- `time-machine` and the `clock` fixture move the monotonic reading of `core/clock.py`, so a check of 301 seconds needs no wait.
- Not testable without a patch, so the logic moved: the mount check of the gate root reads `/proc/mounts` through a module constant. `gate_root_warnings(root, mounts_text)` takes the text, as `slow_mount_fstype` does.
- Not observable through the command, so the assertion left the test: the sum of the durations of the checks (`test_coverage_row_carries_no_duplicated_duration` now reads the duration column of the summary, which shows `-` for the coverage row), and the absence of a name in the `ci` module (`"run_subprocess_async" in vars(ci_module)`), which only mattered while a test patched that module.
- Two tests ran a real ruff (`test_lint_fails_on_an_error_only_the_worktree_has` and its pair). The suite starts no system program, so they now answer ruff from the process fake by the files of its directory. They check that the gate runs lint in the worktree and not in the checkout around it, which is what they were written for.

## Existing Tool Considered

- `process_fake`, `git_fake`, the `clock` fixture (time-machine), `monkeypatch.chdir` and `tmp_path` cover the need. The fakes were built by #1313 to #1325, so this change builds no double.
- `tracked_blobs` and `ci_root` are about 30 lines of fixture code. The cost is about 6,000 tokens to write and 1,000 each month to keep. A fixture of the `ci_root` kind is needed by two directories of tests, so it lives in `tests/support/`.
- The change deletes the two accommodations in `commands/ci.py`, `_run_all_checks`, the `force` argument, `_make_ci_git_fake`, `_refuse_to_start`, and the stale plan folder.
