# Tasks

## 1. Behavior

- [x] 1.1 Write the failing tests: the success set of refine equals the waits of `NextStep`, and an `alternatives` line of the first try is a success and a first pass
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_result.py tests/roadmap/refine/test_roadmap_refine_job_result.py`
- [x] 1.2 Add `alternatives` and `edit` to the success set of refine
  - Verification: `$ uv run devops ci test tests/roadmap/test_job_result.py tests/roadmap/refine/test_roadmap_refine_job_result.py tests/roadmap/test_roadmap_attempt_context.py`

## 2. Documents

- [x] 2.1 Give the new intended result of refine in `docs/roadmap/job-success.md`
  - Verification: `$ uv run devops ci docs`
