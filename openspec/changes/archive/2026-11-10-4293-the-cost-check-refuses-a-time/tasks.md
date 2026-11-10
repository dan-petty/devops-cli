# Tasks

## 1. Accept a time in days, weeks and words

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `tests/roadmap/stage/test_roadmap_stage_cost_units.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_cost_units.py`, assert that a cost with a time in days, in weeks or with a number word is accepted, and that a cost with no count of time or no count of tokens is refused
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_cost_units.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_change.py`, add the units `days` and `weeks` and the number words one to twelve, `a` and `an` to `_TIME_COST`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_cost_units.py tests/roadmap/stage/test_roadmap_stage_content.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
