# Tasks

## 1. Behavior: the limit of refused plans

- [x] 1.1 Write failing tests: the count on the body, a new count after a body edit, the count that another class keeps, the return to New at the limit with the problems or the reason, a problem with a handle, the return in a round of the Service, and a staged item that clears the count
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py`
- [x] 1.2 Add `CONST_ROADMAP_STAGE_PLAN_DEFECT_LIMIT`, the keys `stage.plan_defects` and `stage.plan_defects_body`, `StageFailure.problems` from the planner, the count and the return in `_record_failures`, the clear in `_stage_one`, and the messages of the comment and the log line
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_plan_defect_limit.py tests/roadmap/stage/test_roadmap_stage_failure_class.py tests/roadmap/stage/test_roadmap_stage_retry_after.py`

## 2. Documents

- [x] 2.1 State the count and the return in `docs/roadmap/stage.md`, in the job record table of `docs/ROADMAP_WORKFLOW.md` and in the docstring of the stage module, then regenerate the documents for the new messages
  - Verification: `$ uv run devops ci docs`

- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
