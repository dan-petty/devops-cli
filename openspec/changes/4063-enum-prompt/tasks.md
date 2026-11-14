# Tasks

## 1. Co-locate an enum change with its prompt update

Reads: `src/devops_cli/ai/tasks/roadmap_stage_change.md`. Changes: the same file and `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [ ] 1.1 Add the co-location rule to the prompt.
- [ ] 1.2 Add the prompt-rule test.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py` passes
