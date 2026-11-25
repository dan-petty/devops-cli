# Tasks

## 1. Behavior

- [x] 1.1 Add failing regression tests for `acceptance_criteria`, `criterion_problems`, `section_text`, and `issue_inputs` (`tests/roadmap/stage/test_roadmap_stage_criteria.py`, `tests/roadmap/implement/test_roadmap_implement_step.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py tests/roadmap/implement/test_roadmap_implement_step.py`
- [x] 1.2 Stop open sections at `block_marker_of` in `acceptance_criteria` and `section_text`, and run `section_text` before `_without_comments` in `issue_inputs` (`src/devops_cli/roadmap/stage/stage_criteria.py`, `src/devops_cli/roadmap/step_files.py`, `src/devops_cli/roadmap/implement/implement_step.py`)
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_criteria.py tests/roadmap/implement/test_roadmap_implement_step.py`

## 2. Documents

- [x] 2.1 Run OpenSpec and static quality gates across all modified files
  - Verification: `$ uv run devops openspec check`
