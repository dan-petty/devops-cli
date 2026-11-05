# Proposal

## Why

A behavior group starts with a failing test (AGENTS.md rule 4). The implement step does not check that this test fails on the base commit, or that it passes after the change. A test that never failed proves nothing. This change adds that check to the implement step (#3042).

## What Changes

- For a behavior group, the step replays the test files of the group on the base commit of the group, with the head's tests overlaid. A group whose tests pass on the base is refused. A group whose tests only error on the base, such as a collection error, is refused too. The step gives one repair round for these refusals, and the round may change only test files.
- A group that changes no test file is refused. It gets no repair round.
- The step records each base replay as a check event of the trace, with its exit status.
- The PR comment shows the fail-to-pass result of each behavior group.
- A group of kind `other` runs its verify commands, as before. The PR comment now shows the masked, bounded output of each command.
- Carry a spec delta: a refusal, a repair round and a PR comment line are behavior that a person observes.
- The change fits one pull request. It closes only #3042.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `roadmap-implement-step`: ADDED requirements for the fail-to-pass check of a behavior group, the trace event of the replay, the PR comment line of each behavior group, and the recorded output of a group of kind `other`.

## Impact

- Code: `src/devops_cli/roadmap/implement_base_replay.py` (new), `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_tool_log.py`, `src/devops_cli/roadmap/implement_run.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/plan_read.py`, `src/devops_cli/ci/fail_to_pass.py`, `src/devops_cli/lang/en/messages.py`
- Documents: `docs/roadmap/implement.md`
- Tests: `tests/roadmap/test_roadmap_implement_step_fail_to_pass.py` (new), `tests/roadmap/test_roadmap_implement_step_trace.py`, `tests/roadmap/test_roadmap_implement_job.py`

## Feasibility

- Checked at `origin/main` 0a62030c (2026-11-05) with `git show origin/main:<path>` and `grep -n`.
- `_exit_failure` in `src/devops_cli/roadmap/implement_step.py` runs `commands_failure` on the verification commands of the group, in the checkout after the change (line 1182). No code runs a command on the base commit. The only read of the base is `_tests_failure`, which checks that no test was lost.
- `ImplementTrace.check` in `src/devops_cli/roadmap/implement_trace.py` (line 134) keeps the command and the exit status only. The trace has no output by design.
- `_comment` in `src/devops_cli/roadmap/implement_run.py` (line 1143) builds the PR comment from the step table and the scoped lines. It has no fail-to-pass line.
- `GroupKind` in `src/devops_cli/roadmap/stage_change.py` (line 267) and the stage template `stage_task_test` (`src/devops_cli/lang/en/messages.py`, line 3390) hold the `behavior` kind and the `fails on the base` suffix. The implement step does not read them yet.
- `src/devops_cli/ci/fail_to_pass.py` has `materialise_base_with_head_tests` (line 259) and `pytest_replay_argv` (line 285). The check reuses both.

## Existing Tool Considered

The open tools are pytest with `--junitxml`, which separates a failed call from a collection error, and `git worktree`, which gives the base tree. `src/devops_cli/ci/fail_to_pass.py` already uses both for the fail-to-pass gate of pull requests. This change reuses that module through one public function, and adds no new tool. The written cost of the glue code in the implement step is about 60k tokens to build, 20k tokens to keep and fix, and about 2 hours of elapsed time. The change deletes no internal code.
