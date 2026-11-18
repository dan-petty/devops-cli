# Tasks

## 1. Do not create empty groups for whole-suite criteria

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/ai/tasks/roadmap_stage_split.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 1.1 Add a prompt rule test asserting that `roadmap_stage_change.md` and `roadmap_stage_split.md` forbid empty task groups and map whole-suite criteria to the completing group
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 1.2 Update `src/devops_cli/ai/tasks/roadmap_stage_change.md` and `src/devops_cli/ai/tasks/roadmap_stage_split.md` to forbid docstring-only task groups and map global criteria to the completing group
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## Criteria

- Group 1: The stage prompts SHALL state that global, performance, or hermeticity criteria MUST be mapped to the task group that delivers or completes the suite.
- Group 1: The stage prompts SHALL forbid creating task groups that only update docstrings or restate instructions.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
