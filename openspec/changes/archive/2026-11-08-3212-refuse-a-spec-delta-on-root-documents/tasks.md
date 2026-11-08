# Tasks

## 1. Refuse a spec delta on root documents and manuals

Reads: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`. Changes: `src/devops_cli/roadmap/stage/stage_change.py`, `src/devops_cli/ai/tasks/roadmap_stage_change.md`, `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`.

- [x] 1.1 In `tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`, update `test_the_check_wants_a_spec_delta_for_a_path_outside_the_list` to use an observable source path instead of `README.md`, and add tests for root documents and knowledge-base manuals
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`
- [x] 1.2 In `src/devops_cli/roadmap/stage/stage_change.py`, add `src/devops_cli/ai/knowledge_base/` to `_NO_SPEC_PREFIXES`, add helper `_is_no_spec_path`, and update `_needs_no_spec`. Update line 18 in `src/devops_cli/ai/tasks/roadmap_stage_change.md`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_prompt_rules.py`

## 2. Judge recorded defect of case 2526

Reads: `tests/fixtures/roadmap_eval/stage/2526-the-five-defect-fixes-merged-on/case.json`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`. Changes: `tests/fixtures/roadmap_eval/stage/2526-the-five-defect-fixes-merged-on/case.json`, `tests/roadmap/stage/test_roadmap_stage_eval_gates.py`, `tests/roadmap/stage/test_roadmap_stage_eval_command.py`.

- [x] 2.1 In `tests/fixtures/roadmap_eval/stage/2526-the-five-defect-fixes-merged-on/case.json`, set gate to `paths` and remove the `reason` key for the `spec_delta_wrong` defect
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py`
- [x] 2.2 In `tests/roadmap/stage/test_roadmap_stage_eval_gates.py` and `tests/roadmap/stage/test_roadmap_stage_eval_command.py`, verify the replay of case 2526 catches the `spec_delta_wrong` defect with gate `paths`, and update baseline counts
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_eval_gates.py tests/roadmap/stage/test_roadmap_stage_eval_command.py`

## 3. Align the plan check test with the new problem text

Reads: `tests/roadmap/stage/test_roadmap_stage_plan.py`. Changes: `tests/roadmap/stage/test_roadmap_stage_plan.py`.

- [x] 3.1 In `tests/roadmap/stage/test_roadmap_stage_plan.py`, update `NO_SPEC_PROBLEM` to include `src/devops_cli/ai/knowledge_base/`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan.py`

## Criteria

- Group 1: The stage proposal check SHALL refuse a proposal with a spec delta when every changed path is a root markdown document or is under `src/devops_cli/ai/knowledge_base/`.
- Group 1: The stage proposal check SHALL accept a proposal with `skip_specs: true` when every changed path is under `src/devops_cli/ai/knowledge_base/` or `tests/`.
- Group 1: The stage prompt SHALL name root documents and `src/devops_cli/ai/knowledge_base/` in its `skip_specs` sentence.
- Group 2: The replay of case 2526 SHALL judge the `spec_delta_wrong` defect with gate `paths`.

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
