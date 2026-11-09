# Tasks

## 1. Refused replies and the degenerate stop

- [x] 1.1 Write the failing tests for the refused file, the log line, the degenerate stop, the metric result and the eval count
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py tests/roadmap/stage/test_roadmap_stage_eval_run.py`
- [x] 1.2 Add `RefusedRecord`, `RoadmapStageDegenerateError`, `RunTrace.last_input_tokens`, the log line, `StageResult.DEGENERATE` and `Outcome.DEGENERATE`
  - Verification: `$ uv run devops ci test tests/roadmap/stage/test_roadmap_stage_refused_reply.py tests/roadmap/stage/test_roadmap_stage_eval_run.py`

## 2. Documents

- [x] 2.1 Update the Service item of `k8s/README.md` and regenerate the metric table
  - Verification: `$ uv run devops ci docs`

## Workflow follow-up

- Criteria 4 and 5 of #4204 (the `staged` count above 0 in each 24 hours, and the named cause) are the results of merged fixes. #4205 holds them.
- The text of the violations of a `StructuredOutputValidationError` in the log is not part of this change.
- Pending a person: review the diff in tuicr (tuicr -r <base>..HEAD).
