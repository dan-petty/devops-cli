# Tasks

## 1. Return the message-file problem from the stage content check

Reads: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`, `tests/support/roadmap_stage.py`. Changes: `src/devops_cli/roadmap/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/test_roadmap_stage_plan.py`.

- [ ] 1.1 Add two cases to `tests/roadmap/test_roadmap_stage_plan.py`: one where a task text names `MESSAGES.roadmap` and no group lists `src/devops_cli/lang/en/messages.py`, which must return a problem naming that file, and one where a group lists it, which must return no such problem
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` fails on the base
- [ ] 1.2 Add a `stage_problem_*` entry to the `RoadmapMessages` catalog in `src/devops_cli/lang/en/messages.py`, and in `content_problems` in `src/devops_cli/roadmap/stage_change.py`, collect the rendered task texts of every group with `_task_texts` and match `MESSAGES.roadmap` with an optional dotted attribute. When a text matches and no group lists `src/devops_cli/lang/en/messages.py` in `changes`, append the new problem text
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py` passes

## 2. Name missing_path in the verification prompt

Reads: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `tests/roadmap/test_roadmap_stage_verify.py`, `src/devops_cli/roadmap/stage_change.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, `tests/roadmap/test_roadmap_stage_verify.py`.

- [ ] 2.1 Widen the `missing_path` bullet in `src/devops_cli/ai/tasks/roadmap_stage_verify.md`, still one definition of the type, so a code change that needs a file that the plan does not change is also a `missing_path`, and add a case to `tests/roadmap/test_roadmap_stage_verify.py` that reads the prompt and asserts the bullet names that case
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_verify.py` passes

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
