# Tasks

## 1. Make the cut of a tool answer visible

Reads: `src/devops_cli/roadmap/refine/refine_investigation.py`. Changes: `src/devops_cli/roadmap/refine/refine_investigation.py`, `tests/roadmap/stage/test_roadmap_stage_tools.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_tools.py`, assert that `cut` and `read_file` end at a whole line with the notice when the character limit drops lines
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/refine/refine_investigation.py`, cut at whole lines and write the notice for both limits
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_tools.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
