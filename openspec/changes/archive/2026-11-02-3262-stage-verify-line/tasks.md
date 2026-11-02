# Tasks

## 1. The stage job writes the Verification line

Kind: behavior. Reads: `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_kind.py`. Changes: `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_task_verification.py` (new), `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/roadmap/__snapshots__/test_roadmap_stage_plan.ambr`.

- [x] 1.1 In `tests/roadmap/test_roadmap_stage_task_verification.py`, add the round trip from `StageGroup` through `group_text` and `render_change` to `parse_task_groups`: a behavior group, an other group, a group with a manual check, a group with documentation, the line of each task, and each valid group of the golden set `tests/fixtures/roadmap_eval/stage`, among them the five groups of #2175
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_task_verification.py` fails on the base: `67 failed, 2 passed`
- [x] 1.2 In `src/devops_cli/lang/en/messages.py`, change `stage_task_test`, `stage_task_pass` and `stage_task_documents` to write the command on a `Verification:` line under the task. In `tests/roadmap/test_roadmap_stage_kind.py`, `tests/roadmap/test_roadmap_stage_plan.py` and its snapshot, write the new text
  - Verification: `uv run devops ci test tests/roadmap` passes
