# Tasks

## 1. Log lines with counts for each fix round, failed item and implement attempt (behavior)

- [x] 1.1 Write failing tests: a pass after a return and two review rounds, a revision that stays refused, a failed item of the stage row, and an ended implement Job each log their line.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py tests/roadmap/stage/test_roadmap_stage_round_log.py tests/roadmap/implement/test_roadmap_implement_submit.py`
- [x] 1.2 Add `src/devops_cli/roadmap/round_log.py`, and call it from `_returned` and `_verified` in `src/devops_cli/roadmap/stage/stage.py`, from `_run_stage_adapter` in `src/devops_cli/roadmap/run.py` and from `_report` in `src/devops_cli/roadmap/implement/implement_submit.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_repair_return.py tests/roadmap/stage/test_roadmap_stage_round_log.py tests/roadmap/implement/test_roadmap_implement_submit.py`

## 2. The error line names every failed item (behavior)

- [x] 2.1 Write a failing test: a round whose stage error has a first line over 256 characters names `#1, #2, #3`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_errors.py`
- [x] 2.2 Add the failed items after the cut line in `_format_error_line` of `src/devops_cli/roadmap/run.py`.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_run_errors.py`

## 3. Documents (other)

- [x] 3.1 Name the four lines and the error line in step 15 and in the implement step of `k8s/README.md`.
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
