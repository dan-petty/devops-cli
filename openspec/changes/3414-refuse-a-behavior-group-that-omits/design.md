# Design

## Decisions

- **Record the existing tests of each changed module in the caller, and refuse the group in the `paths` gate**: The `paths` gate is the one rule set of the stage job and the plan recheck, and a caller that runs no search passes no record and judges nothing, as `record_test_references` does for a manifest.
- **Take a candidate test from both the test naming convention and the search of the module name**: `tests/roadmap/implement/test_roadmap_implement_step.py` imports `devops_cli.roadmap.step_files` and its name carries no stem of that module, so the naming convention alone misses the test of the issue.
- **Count a test as named when the group lists it in `reads`, `changes`, a task code span or `verify`**: A group reads a test that pins a module it changes and must not edit it, so a rule over `changes` alone would refuse a correct plan.
- **Leave out every test path that a group lists in `creates`**: A test file that the plan creates is no existing test, and the staged tree holds none of the files that the plan creates.
- **Compare `group.kind` with the string `behavior`**: `stage_paths.py` reads `StageGroup` only under `TYPE_CHECKING`, and a runtime import of `GroupKind` from `stage_change.py` would close the cycle between the two modules; `GroupKind` is a `StrEnum`.
- **Pass no record from `devops roadmap plan-check`**: `plan_check.py` builds its tree from `git ls-tree` with no checkout, so it runs no search; the stage job and the plan recheck, which hold a checkout, pass the record.

## Rejected alternatives

- **Extend `path_problems` itself with the rule**: `src/devops_cli/roadmap/stage/stage_paths.py:356:def path_problems(` reports a path once and skips a path that an earlier place reported, so one group with two changed modules would give one sentence with no list of the tests to add.
- **Search the checkout inside the gate**: `src/devops_cli/roadmap/stage/stage_eval_gates.py` builds its tree from the case and runs no git, so the record has to come from the caller.
- **Match the test file name to the module stem only**: `tests/roadmap/implement/test_roadmap_implement_step.py:61:from devops_cli.roadmap.step_files import parse_task_groups` shows a test whose name carries no stem of `step_files`.
- **Run the test suite to find the test of a module**: The stage job validates a reply in seconds and installs no dependency for a suite, and one search gives the same answer on each run.
- **Require the existing test in `changes` only**: A group reads a test that pins the module it changes and must not edit it, so `changes` alone refuses a correct plan.
