# Tasks

## 1. Name both forms in the missing-path message

Reads: `src/devops_cli/roadmap/stage_paths.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_paths.py`. Changes: `src/devops_cli/lang/en/messages.py`, `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_stage_paths.py`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_paths.py`, assert that the problem of a group that names a missing path holds `creates`, ` (new)` and `Changes:`, that it ends with the `stage_path_same_name` hint, and that a path a later group creates keeps its own message
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` fails on the base
- [x] 1.2 Rewrite `MESSAGES.roadmap.stage_problem_path` in `src/devops_cli/lang/en/messages.py` to name the `creates` list of a reply and the ` (new)` mark of the `Changes:` line, and keep the placeholders `{group}`, `{path}`, `{place}` and `{hint}`. State in the docstring of `src/devops_cli/roadmap/stage_paths.py` that `path_problems` judges both the stage reply and the change folder. Leave the later-creator message as it is
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_paths.py` passes

## 2. Assert the message through the plan check

Reads: `src/devops_cli/roadmap/plan_check.py`, `src/devops_cli/roadmap/stage_paths.py`, `tests/roadmap/test_roadmap_plan_check.py`. Changes: `tests/roadmap/test_roadmap_plan_check.py`.

- [ ] 2.1 In `tests/roadmap/test_roadmap_plan_check.py`, assert that a change folder whose group `Changes:` line names a new file with no ` (new)` mark reports a problem that holds ` (new)` and `Changes:`
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_plan_check.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
