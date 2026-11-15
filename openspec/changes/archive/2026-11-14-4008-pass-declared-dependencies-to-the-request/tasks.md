# Tasks

## 1. Carry the declared dependencies in the request

Reads: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/roadmap/refine/refine.py`.

Changes: `src/devops_cli/roadmap/stage/stage.py`, `src/devops_cli/roadmap/stage/stage_request.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_plan.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, `tests/roadmap/stage/test_roadmap_stage_request.py`.

- [x] 1.1 Write the request test and the prompt rule, and watch them fail.
  - Verification: `$ uv run devops ci test tests/roadmap/stage`
- [x] 1.2 Add the field, the store lookup and the prompt sentences.
  - Verification: `$ uv run devops ci test tests/roadmap/stage`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
