# Tasks

## 1. Return a refused revision

Reads: `src/devops_cli/roadmap/stage/stage.py`. Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_repair_return.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_repair_return.py`, assert that a revision the checks refuse once goes back and the second passes, that a revision refused twice ends the item with the problem and no third call, and that the refused file holds the revisions
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py` fails on the base
- [x] 1.2 Add `CONST_ROADMAP_STAGE_GATE_RETURNS` and the failure text, and move the return into `_Planner._returned`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py tests/roadmap/stage/test_roadmap_stage_refused_reply.py tests/roadmap/stage/test_roadmap_stage_verification.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that 81 of 317 defects are caught by a gate, none is missed and 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`
