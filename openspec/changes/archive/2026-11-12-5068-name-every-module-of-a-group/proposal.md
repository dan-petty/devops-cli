# Proposal: #5068

## Why

The module-test check of the stage `paths` gate (#3414) names only the first module of a behavior group that has no named test. `_unnamed_module_test` in `src/devops_cli/roadmap/stage/stage_paths.py` returns at the first such module of `group.changes`, so `existing_test_problems` gives one problem for each group. The repair round fixes that module, and the next reply is refused for the next module of the same group. Each module uses one gate return, and the stage gate has 3 returns, so a group that changes 3 or more modules with separate tests is refused although one repair could fix all of them. Closes #5068.

## What Changes

- `_unnamed_module_test` becomes `_unnamed_module_tests`: it gives each module of the group whose tests the group names nowhere, with its nearest test, in the order of `changes`.
- A test that the problem of an earlier module asks for counts as named for each later module of the same group, so the gate asks for no second test of a module that the asked test also runs.
- `existing_test_problems` gives one problem for each module. The message, its finding class and the accept rule do not change.
- The requirement "Report one problem for each group that omits its test" of `roadmap-stage/tests-gate` becomes "Report one problem for each module whose test a group omits".
- `docs/roadmap/plan-check.md` and `docs/ROADMAP_WORKFLOW.md` state that one refusal names each such module.

## Capabilities

- `roadmap-stage/tests-gate`: the module-test check names every module of a group whose test the group omits, in one result.

## Impact

- A refused plan gets every missing module test in one refusal, so the repair round can fix the group at once and a group with many modules no longer uses one gate return for each module.
- The gate accepts and refuses the same plans as before. It gives no problem for a group only when each module of the group has a named test, as on `origin/main`.
- A refusal can hold more problems than before, one for each module.

## Feasibility

- `origin/main` at cf4733e00 holds `return path, tests[0]` inside the loop over `group.changes` in `_unnamed_module_test` (`src/devops_cli/roadmap/stage/stage_paths.py:618-629`), and `existing_test_problems` appends at most one problem for each group.
- The new test `test_the_paths_gate_names_every_module_of_a_group_that_omits_its_tests` fails on `origin/main`: the result holds the problem of `step_files.py` and not the problem of `follow.py`.
- The stored stage traces of 2026-11-10 and 2026-11-11 hold the split: #2530 group 1 was refused for `constants.py` and then for `messages.py`, and #3387 group 5 for `stage.py` and then for `store.py` (`tests/ai/review/test_support_builders.py`), each in a later repair round.
- The same recorded replies, run through `record_module_tests` and `existing_test_problems` of `origin/main` and of this change with the tree of `origin/main`, give the same accept result for each reply and the same number of problems. The record of #4467 and #4519 now gives a shared test for the modules of those groups: `tests/github/test_merge_readiness.py` for #2530 and `tests/roadmap/stage/test_roadmap_stage_apply.py` for #3387. The defect stays for a group whose modules have separate tests, as the new test shows.
- `uv run devops roadmap eval stage --replay` gives the same result on `origin/main` and on this change: its cases hold no file reader, so it records no module test (#4506).

## Existing Tool Considered

The check is a loop over the record that `record_module_tests` already gives; no open library holds the stage plan rules. Cost to build: about 150,000 tokens and 1.5 hours; to keep: about 1,000 tokens a month.
