# Tasks

## 1. Behavior

- [x] 1.1 Add failing tests for group files limit and prefix move exemption
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_group_files.py`
- [x] 1.2 Implement `group-files` gate, prefix move exemption, and message catalog entry
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_group_files.py`

## 2. Documents

- [x] 2.1 Update staging prompts, telemetry instruments, and workflow documentation
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
  - Verification: `$ uv run devops ci test tests/telemetry/test_roadmap_stage_steps.py`
