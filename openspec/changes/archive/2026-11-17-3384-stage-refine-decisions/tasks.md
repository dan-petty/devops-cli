# Tasks

## 1. Prompt and refusal for refine design

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_criteria.py`. Changes: `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/lang/en/messages.py`, `tests/roadmap/stage/test_roadmap_stage_content.py`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 1.1 Write failing tests in `tests/roadmap/stage/test_roadmap_stage_content.py` and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 1.2 Update prompt `src/devops_cli/ai/tasks/roadmap_stage_change.md`.
- [x] 1.3 Add `refine_decisions` in `src/devops_cli/roadmap/stage/stage_criteria.py`.
- [x] 1.4 Add refusal check in `src/devops_cli/roadmap/stage/stage_change.py` and error messages in `src/devops_cli/lang/en/messages.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_content.py tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
