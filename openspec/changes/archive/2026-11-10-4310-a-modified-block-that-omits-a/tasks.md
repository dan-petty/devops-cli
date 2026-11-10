# Tasks

## 1. Restore the omitted scenarios

Reads: `src/devops_cli/roadmap/stage/stage_validate.py`, `src/devops_cli/roadmap/stage/stage_change.py`. Changes: `src/devops_cli/roadmap/stage/stage_validate.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage.py`, `tests/roadmap/stage/test_roadmap_stage_restore_scenarios.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_restore_scenarios.py`, assert that the files of a plan whose MODIFIED requirement omits a base scenario hold all base scenarios, and that a complete block, an unknown requirement and an ADDED requirement stay as they are
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_restore_scenarios.py` fails on the base
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_validate.py`, add `restore_omitted_scenarios`, render the block with `spec_file` in `src/devops_cli/roadmap/stage/stage_change.py`, and call the repair in `_settle` of `src/devops_cli/roadmap/stage/stage.py` before the validation
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_restore_scenarios.py tests/roadmap/stage/test_roadmap_stage_plan.py` passes

## 2. Keep the golden replay

- [x] 2.1 Run the replay and state that every gate refuses what it must refuse and that 5 of 5 good plans pass
  - Verification: `$ uv run devops roadmap eval stage --replay`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
