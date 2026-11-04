# Tasks

## 1. Return the message-file problem from the stage content check

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 1.1 Add two cases to `tests/roadmap/test_roadmap_stage_plan.py`: one where a task text names `MESSAGES.roadmap` and no group lists `src/devops_cli/lang/en/messages.py`, which must return a problem naming that file, and one where a group lists it, which must return no such problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 In `content_problems` in `src/devops_cli/roadmap/stage_change.py`, collect the rendered task texts of every group and match `MESSAGES.roadmap` with an optional dotted attribute. When a text matches and no group lists `src/devops_cli/lang/en/messages.py` in `changes`, append a problem that names the file
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Name missing_path in the verification prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`.

- [ ] 2.1 Add a line to `src/devops_cli/ai/tasks/roadmap_stage_verify.md` that types a code change which needs a file the plan does not change as `missing_path`, so the pass returns the plan to the planner once
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_task_verification.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
