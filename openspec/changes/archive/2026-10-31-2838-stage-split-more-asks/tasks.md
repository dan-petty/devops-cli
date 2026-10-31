# Tasks

## 1. The measure of a group counts each file as the step reads it

- [x] 1.1 Add failing tests: a group that names a file of far more tokens than the budget measures under the budget and costs no split call; the measure of a file equals the tokens of `packed_file`; the step and the measure use the same text; adapt the tests of the split to groups that name many files
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_implement_step.py`
- [x] 1.2 Add `roadmap/step_files.py` with `packed_file`; make `implement_step` and `stage_change.measure_groups` call it; delete `_packed`, `_packed_tokens` and the `limit` argument
  - Verification: `uv run devops ci test tests/roadmap/test_roadmap_stage_plan.py tests/roadmap/test_roadmap_implement_step.py`
- [x] 1.3 Say in the module text of `stage.py` that a file counts at most the file cap of the step, and run `uv run devops docs generate --sync-readme`
  - Verification: `uv run devops ci docs`

## Workflow follow-up

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
