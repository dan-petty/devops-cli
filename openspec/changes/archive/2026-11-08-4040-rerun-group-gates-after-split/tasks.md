# Tasks

## 1. Judge a split with the gates of the first reply

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `tests/support/roadmap_stage.py`, `openspec/specs/roadmap-stage/spec.md`. Changes: `tests/roadmap/stage/test_roadmap_stage_split_gates.py`, `src/devops_cli/roadmap/stage/stage.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_split_gates.py`, write a case for each fault that only one gate refuses: a trigger path with no replay task, a What Changes path that no group lists, a move with a missing module of the prefix, and a registry item with no task for its test module. Each case scripts a first plan that passes, a split that brings the fault, and a corrected reply. One test asserts that the planner sends the problem back. A second test asserts that `check_gates` finds problems under exactly one gate name, and that the planner sends that problem
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_split_gates.py` fails on the base
- [x] 1.2 In `_Planner._settle` in `src/devops_cli/roadmap/stage/stage.py`, replace the hand-made list of five gates after a split with a call to `check_proposal` on the split proposal. Pass the arguments of the first pass: the tree with the files of the split, the search evidence recorded for the new groups, and the constants of the new plan texts. Remove the imports that no code uses
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_split_gates.py` passes
- [x] 1.3 Run the tests of the stage job that the change can touch and the check of the hand-made list
  - Verification: `$ ! git grep -n path_problems src/devops_cli/roadmap/stage/stage.py`

## Criteria

- Group 1: A scripted split that brings back a trigger path with no replay task, a What Changes path that no group lists, a move with a missing module of the prefix, or a missing registry place SHALL go back to the model with the problem of the gate that refuses it, and on the unchanged code the planner accepts each of the four plans.
- Group 1: For each scripted split, `check_gates` SHALL show problems under exactly one gate name.
- Group 1: `src/devops_cli/roadmap/stage/stage.py` SHALL hold no call of `path_problems`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
