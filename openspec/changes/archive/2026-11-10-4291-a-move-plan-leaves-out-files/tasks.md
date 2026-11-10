# Tasks

## 1. Derive a move from the module in another place

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/docs/inventory.py`, `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_move_references.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_move_references.py`, assert that a group that changes a module and creates a test, a document or a module of another name moves nothing, that a group that creates the module under a sub-package or in another folder moves it, and that a probed file of class `tool-owned` or `record` needs no task group while a hand-written document, a test and a caller still do
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_move_references.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_change.py`, derive a moved module from a created module of the same name or under the sub-package of the name prefix, and skip a probed file of class `tool-owned` or `record` in `_move_reference_problems`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_move_references.py tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
