# Design

## Context

`_exit_failure` in `src/devops_cli/roadmap/implement_step.py` runs the verification commands of a group after the agent returns. It does not run any test on the base commit. The base commit of a group is `keeper.base`, the commit where the group starts. A replay of the group's tests on that commit shows whether they fail there.

`src/devops_cli/ci/fail_to_pass.py` already replays test files on a base tree. It materialises the base as a detached worktree, overlays the head's `tests/`, runs pytest with `--junitxml`, and removes the worktree.

## Goals and Non-Goals

Goals:

- A behavior group's test files fail on the base commit before the change, for the right reason.
- The trace and the PR comment show the result of the replay.
- A group of kind `other` shows the output of its verify commands in the PR comment.

Non-Goals:

- Change the fail-to-pass gate of pull requests (`devops ci fail-to-pass`).
- Apply the unchanged-failure filter of #3124 to the group's tests. The test files of a group are new or changed by the group itself.
- Put command output in the trace. The trace holds no output by design.

## Decisions

- **The base is the group's start.** The replay uses `keeper.base`, the first commit that is not a `wip:` commit of the step. Rejected: the merge base with `origin/main`. A later group would then count the code of an earlier group as new.
- **The test run is pytest with JUnit, through `ci/fail_to_pass.py`.** A group's verify command gives only an exit code, and that code does not tell a failed call from a collection error. The JUnit report does. Rejected: exit code only, because a collection error would count as a failure.
- **The group is proven when one of its tests fails in its call phase on the base.** A file may hold a regression test that passes on the base, so every test is not required to fail. Rejected: every test must fail, because it refuses a valid regression test in the same file.
- **A collection error is not a failure on the base.** A test that cannot be collected does not show a failed assertion. The step refuses it with a repair round.
- **Refusals get one repair round, limited to the test files.** The fix is a test that fails first. The repair turn may change only the test files and `tasks.md`. This follows D1 of the issue.
- **A group that changes no test file is refused without a repair round.** A repair turn that may change only test files cannot write a test that is not there. Rejected: a repair round with an empty set of paths, because the turn could then change nothing useful.
- **The kind `behavior` is read from the tasks file.** A group is `behavior` when its text holds `Kind: behavior.` or when its first task's `Verification:` line ends with `fails on the base`. The plan reader in `src/devops_cli/roadmap/plan_read.py` uses the same rule. The suffix constant moves to `step_files.py`, so both modules read one value.
- **The output of a group of kind `other` is masked and bounded.** The step uses `_tail`, which escapes each line and cuts it, and `mask_secrets`. The PR comment shows the output in a code fence.

## Risks

- A test that imports a new name at module level errors on the base. The repair turn must move the import into the test function. The refusal message says so.
- The replay runs pytest in the base tree. The base tree uses the `pythonpath = ["src"]` setting of `pyproject.toml`, so it imports the base code. This setting exists on `origin/main`.
- Each replay adds one pytest run and one worktree. The step keeps this run inside the command timeout of the step.

## Existing Tool Considered

Pytest with `--junitxml` and `git worktree`, through `src/devops_cli/ci/fail_to_pass.py`. No new tool is added. The glue code in the implement step is about 60k tokens to build, 20k tokens to keep and fix, and about 2 hours of elapsed time.
