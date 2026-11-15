# Tasks

## 1. Failure class and exception

- [x] 1.1 Add `RoadmapPlanReadBackError` and `FailureClass.PLAN_UNREADABLE`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_failure.py`
- [x] 1.2 Add `READ_GATE` in `stage_findings.py` and import in `plan_recheck.py`
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_recheck.py`

## 2. Read-back comparison

- [x] 2.1 Implement `read_back_problems` in `plan_read.py`
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_plan_read.py -k test_read_back_problems`
- [x] 2.2 Wire read-back and gate check into `_Planner._settle` and `_file_findings`
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_plan.py -k test_a_reply_whose_text_the_reader_refuses`

## 3. Stage and fix-plan integration

- [x] 3.1 Record `plan_unreadable` toward defect limit in `stage.py`
  - Verification: `$ uv run pytest tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py -k test_plan_unreadable`
- [x] 3.2 Update dry-run message in `messages.py` and fix-plan tests
  - Verification: `$ uv run pytest tests/commands/test_roadmap_step_fix_plan.py -k test_the_dry_run`

## 4. Documentation and specs

- [x] 4.1 Update documents, workflow guide, and spec deltas
  - Verification: `$ uv run devops ci docs`
