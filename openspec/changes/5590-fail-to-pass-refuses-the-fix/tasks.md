# Tasks

## 1. Replay the unchanged failures on the head tree and refuse only a test that does not pass there

Kind: behavior. Reads: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/ci/changed_tests.py`, `src/devops_cli/lang/en/messages.py`, `tests/ci/test_fail_to_pass.py`. Changes: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`, `tests/ci/test_fail_to_pass.py`.

- [ ] 1.1 `tests/ci/test_fail_to_pass.py::test_an_unchanged_test_that_the_head_repairs_does_not_refuse_the_replay` fails first: the check refuses the repaired test today because it runs no pytest on the head tree
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` fails on the base
- [ ] 1.2 Write the failing tests first in `tests/ci/test_fail_to_pass.py`: `test_an_unchanged_test_that_the_head_repairs_does_not_refuse_the_replay`, `test_a_repair_alone_does_not_satisfy_the_replay`, `test_a_head_replay_that_could_not_run_refuses_the_replay`, and update `test_a_test_that_the_fix_leaves_alone_and_that_fails_on_base_refuses_the_replay` to a test that still fails on the head. Add `head_junit_xml` and `head_exit_status` to `_FailToPassState` and make `_pytest_answer` answer a call outside the folder named `tree` with them, so the base run and the head run differ; add the new keys to `_replay_report`. Then change `src/devops_cli/ci/fail_to_pass.py`: add `repaired` and `head_could_not_run` to `FailToPassReport` and narrow the docstring of `unchanged_failed`; add `changed_failed_count`, which counts a failed outcome that is neither unchanged nor repaired, and use it in `satisfied`; add `head_could_not_run is not None` to `tests_refused`. Add the context manager `_head_tree(root, head, dest)`, which yields `root` for `HEAD` and otherwise adds a detached worktree of `head` at `dest` and removes it, and delete `_run_gate_rows_on_head` in its favor. Rename `_run_pytest_on_base` to `_run_pytest_replay`. Add `_files_holding(ids, outcomes, files)` and `_repaired_and_refused(unchanged, head_outcomes)`, which splits the unchanged failures into the ones that the head passes and the ones that it does not. In `run_fail_to_pass`, open `_head_tree` only when a gate row or an unchanged failure exists, run the head replay of the files that hold an unchanged failure there, run the head gate rows there, and fill `repaired`, `unchanged_failed` and `head_could_not_run` from the split. In `src/devops_cli/lang/en/messages.py`, reword `fail_to_pass_unchanged_failed` to name the head and add `fail_to_pass_repaired` and `fail_to_pass_head_could_not_run`. In `_unsatisfied_reasons`, add the head could-not-run branch before the unchanged branch, and in `format_fail_to_pass_report` print the repaired line after the per-test lines
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` passes

## 2. List the head replay in the dry run

Kind: behavior. Reads: `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/dry_run/requests.py`, `tests/ci/test_fail_to_pass.py`. Changes: `src/devops_cli/ci/fail_to_pass.py`, `tests/ci/test_fail_to_pass.py`.

- [ ] 2.1 `tests/ci/test_fail_to_pass.py::test_fail_to_pass_dry_run_lists_the_head_replay` fails first: the plan lists no head pytest run today
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` fails on the base
- [ ] 2.2 Write `test_fail_to_pass_dry_run_lists_the_head_replay` first, which asserts that the plan of `devops ci fail-to-pass --dry-run` holds the head pytest run with the condition `a test that failed on base is unchanged` and records no process call. Then change `plan_fail_to_pass` in `src/devops_cli/ci/fail_to_pass.py`: add the constants `UNCHANGED_REPLAY`, `HEAD_RUN` and `UNCHANGED_TESTS_PLACEHOLDER`, list the head pytest run with the new JUnit path after the removal of the base worktree, give the named-head worktree add, remove and prune the condition `HEAD_RUN`, and keep the head gate row with `GATE_REPLAY`. Update `test_fail_to_pass_dry_run_lists_the_replay_and_starts_nothing` and `test_fail_to_pass_dry_run_of_a_head_lists_the_fallback_diff` for the new lines and indices. `test_fail_to_pass_runs_the_processes_of_its_plan` keeps its skip rule: `HEAD_RUN` starts with `a changed gate check exists` and the head pytest condition holds `failed on base`, so a replay that ran no test skips both
  - Verification: `$ uv run devops ci test tests/ci/test_fail_to_pass.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
