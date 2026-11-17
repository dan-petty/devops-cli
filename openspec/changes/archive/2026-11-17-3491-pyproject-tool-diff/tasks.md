# Tasks

## 1. Implement diff-aware pyproject.toml classification

Kind: behavior. Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/roadmap/stage/stage_eval_cases.py`, `src/devops_cli/roadmap/stage/stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [x] 1.1 Write failing tests in `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` for tool-setting diff refusal and dependency diff acceptance with spec delta
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`
- [x] 1.2 Implement `is_tool_setting_diff` and update `_needs_no_spec`, `_delta_problems`, `check_gates`, `check_proposal`, `CaseFacts`, and `PlanUnderTest`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`

## 2. Update case 2163 in golden set

Kind: manifest. Reads: `tests/fixtures/roadmap_eval/stage/2163-coverage-measures-branches-and-ci-keeps/case.json`, `tests/fixtures/roadmap_eval/stage/2163-coverage-measures-branches-and-ci-keeps/facts.json`. Changes: `tests/fixtures/roadmap_eval/stage/2163-coverage-measures-branches-and-ci-keeps/case.json`, `tests/fixtures/roadmap_eval/stage/2163-coverage-measures-branches-and-ci-keeps/facts.json`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`.

- [x] 2.1 Update `case.json` (gate `paths`, remove `reason`), update `facts.json` with `pyproject_diff`, and update baseline counts in `test_roadmap_stage_eval_gates.py`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`
