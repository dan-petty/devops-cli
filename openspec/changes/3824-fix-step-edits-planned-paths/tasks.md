# Tasks

## 1. Stop a fix step that changes an unnamed path

Kind: behavior. Reads: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_strays.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/lang/en/messages.py`. Changes: `src/devops_cli/roadmap/implement_step.py`, `src/devops_cli/roadmap/implement_strays.py`, `src/devops_cli/roadmap/failure.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_implement_step_fix_paths.py` (new), `tests/roadmap/test_roadmap_failure.py`, `tests/roadmap/test_roadmap_implement_strays.py`.

- [x] 1.1 Write tests: a fix step that edits, adds or deletes an unnamed path stops with the class `outside_plan` and resets the checkout, and one that edits a named path or a file of the change folder ends done
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_fix_paths.py` fails on the base
- [x] 1.2 Add `unplanned_paths`, the check in `_exit_failure`, the class `outside_plan` with the action `wait`, and the reason of the stop
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_implement_step_fix_paths.py tests/roadmap/test_roadmap_failure.py tests/roadmap/test_roadmap_implement_strays.py` passes

## 2. Document the class

Kind: docs. Reads: `docs/ROADMAP_WORKFLOW.md`. Changes: `docs/ROADMAP_WORKFLOW.md`.

- [x] 2.1 Add the class `outside_plan` to the list and the table of failure classes
  - Verification: `git grep -n outside_plan docs/ROADMAP_WORKFLOW.md`

## Criteria

- Group 1: ### Requirement: A fix step changes only the paths that the plan names A fix step SHALL stop with the class outside_plan when it changed, added or deleted a path that the plan does not name.
- Group 1: ### Requirement: The failure classes The failure taxonomy SHALL have these 19 classes.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
