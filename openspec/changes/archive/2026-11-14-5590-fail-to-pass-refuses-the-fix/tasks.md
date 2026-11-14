# Tasks

## 1. Replay the unchanged failures on the plain merge base and the head tree and refuse only an unclean or unrepaired test

Kind: behavior. Reads: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/ci/changed_tests.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `CONTRIBUTING.md`, `tests/ci/test_fail_to_pass.py`. Changes: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/lang/en/help.py`, `CONTRIBUTING.md`, `tests/ci/test_fail_to_pass.py`.

- [x] 1.1 `tests/ci/test_fail_to_pass.py::test_an_unchanged_test_that_the_head_repairs_does_not_refuse_the_replay` fails first: the check refuses the repaired test today because it runs no pytest on the head tree
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` fails on the base
- [x] 1.2 Write the failing tests first in `tests/ci/test_fail_to_pass.py`: `test_an_unchanged_test_that_the_head_repairs_does_not_refuse_the_replay`, `test_an_unchanged_failure_that_passes_on_the_plain_merge_base_refuses_the_replay`, `test_a_repair_alone_does_not_satisfy_the_replay`, `test_a_head_replay_that_could_not_run_refuses_the_replay`, `test_a_named_head_with_an_unchanged_failure_runs_the_replay_in_a_worktree_of_that_head`, and `test_the_default_head_with_an_unchanged_failure_runs_the_replay_in_the_working_tree`. Update `test_a_test_that_the_fix_leaves_alone_and_that_fails_on_base_refuses_the_replay` to assert refusal when the unchanged test still fails on the head. Add `plain_base_junit_xml`, `plain_base_exit_status`, `head_junit_xml` and `head_exit_status` to `_FailToPassState`. Make `_pytest_answer` answer calls in `plain_base` and `head` with their states. Add the new keys to `_replay_report`. Then change `src/devops_cli/ci/fail_to_pass.py`: add `repaired` and `head_could_not_run` to `FailToPassReport`. Add `changed_failed_count` to count failed outcomes that are neither unchanged nor repaired, and use it in `satisfied`. Add `_head_tree` and `_plain_base_tree` context managers. Rename `_run_pytest_on_base` to `_run_pytest_replay`. Add `_files_holding(ids, outcomes, files)` and `_repaired_and_refused(unchanged, plain_base_outcomes, head_outcomes)`. In `run_fail_to_pass`, if unchanged failures exist and no host path guard failure occurred, replay on plain base and head tree. In `src/devops_cli/lang/en/messages.py`, reword `fail_to_pass_unchanged_failed` to name the head, and add `fail_to_pass_repaired` and `fail_to_pass_head_could_not_run`. In `_unsatisfied_reasons`, put the head could-not-run branch after the host path guard branch. In `format_fail_to_pass_report`, print the repaired line after the per-test lines. Update `CONTRIBUTING.md:179` to document the repaired test rule and the plain merge-base check. Update `src/devops_cli/lang/en/help.py:970` (`fail_to_pass_head`) to describe the head replay.
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` passes

## 2. List the head replay in the dry run

Kind: behavior. Reads: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/dry_run/requests.py`, `tests/ci/test_fail_to_pass.py`. Changes: `src/devops_cli/ci/fail_to_pass.py`, `tests/ci/test_fail_to_pass.py`, `docs/CLI_REFERENCE.md`, `docs/commands/ci.md`.

- [x] 2.1 `tests/ci/test_fail_to_pass.py::test_fail_to_pass_dry_run_lists_the_head_replay` fails first: the plan lists no head pytest run today
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` fails on the base
- [x] 2.2 Write `test_fail_to_pass_dry_run_lists_the_head_replay` first. Assert that `devops ci fail-to-pass --dry-run` lists the head pytest run with the condition `a test that failed on base is unchanged` and records no process call. Then change `plan_fail_to_pass` in `src/devops_cli/ci/fail_to_pass.py`: add constants `UNCHANGED_REPLAY`, `HEAD_RUN` and `UNCHANGED_TESTS_PLACEHOLDER`. List the head pytest run with the JUnit path after the removal of the base worktree. Give the named-head worktree add, remove and prune the condition `HEAD_RUN`, and keep the head gate row with `GATE_REPLAY`. Update `test_fail_to_pass_dry_run_lists_the_replay_and_starts_nothing` and `test_fail_to_pass_dry_run_of_a_head_lists_the_fallback_diff` for the new lines and indices. Run `uv run devops docs generate` to synchronize documentation from help text.
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
