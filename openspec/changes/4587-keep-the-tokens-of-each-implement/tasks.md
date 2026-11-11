# Tasks

## 1. Behavior

- [x] 1.1 Add tests: the entry of each step holds the requests, the tokens and the largest request, which equal the `model` events of the step, and the entry of a step with one repair round holds 1 round and the requests of both turns
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_trace.py`
- [x] 1.2 Add `largest_request_tokens` to `_Run` and `StepOutcome`, and write the counts of the step in `_step_spend`
  - Verification: `$ uv run devops ci test tests/roadmap/implement/test_roadmap_implement_job_trace.py tests/roadmap/implement/test_roadmap_implement_step_trace.py tests/roadmap/implement/test_roadmap_implement_phase_marks.py`

## 2. Documents

- [x] 2.1 Describe the entry of a step in `docs/roadmap/implement.md`
  - Verification: `$ uv run devops ci docs`
