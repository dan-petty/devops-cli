# Tasks

## 1. Give a run a call budget

Reads: `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`. Changes: `src/devops_cli/roadmap/stage/stage_tools.py`, `src/devops_cli/roadmap/stage/stage_toolbox.py`, `src/devops_cli/config/constants.py`, `src/devops_cli/lang/en/messages.py`, `src/devops_cli/ai/tasks/roadmap_stage_tools.md`, `src/devops_cli/ai/tasks/roadmap_stage_verify_tools.md`, `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, `tests/roadmap/test_roadmap_limit_classes.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_toolbox.py`, assert that the answers from the budget end with the notice, that a review run has its own budget, that a new run restarts the count, and that the prompts name the constants
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py` fails on the base
- [x] 1.2 Add the constants, the counter in `StageTools`, the start of the count in `ToolboxClient` and the text of the prompts
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_toolbox.py tests/roadmap/test_roadmap_limit_classes.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
