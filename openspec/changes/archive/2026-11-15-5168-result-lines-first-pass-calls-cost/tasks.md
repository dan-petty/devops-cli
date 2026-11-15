# Tasks

## 1. Behavior

- [x] 1.1 Acceptance test for FIRST_PASS table boundary values and first_pass line output
  - Verification: `$ uv run pytest tests/roadmap/test_job_result.py`
- [x] 1.2 Acceptance test for attempt context tracking model calls, tokens, seconds, cost, and GitHub requests
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_attempt_context.py`
- [x] 1.3 Implement FIRST_PASS table and first_pass logging in `job_result.py`
  - Verification: `$ uv run pytest tests/roadmap/test_job_result.py`
- [x] 1.4 Implement AttemptContext in `job_result.py` and integrate with `ledger.py` and `rate_limiter.py`
  - Verification: `$ uv run pytest tests/roadmap/test_roadmap_attempt_context.py`
- [x] 1.5 Implement required counts for refine (`tries`), refine_judge (`round`), alternatives (`returns`), intake (`fallbacks`)
  - Verification: `$ uv run pytest tests/roadmap/`
- [x] 1.6 Implement `RoadmapJob.RETITLE` and retitle result line logging
  - Verification: `$ uv run pytest tests/roadmap/test_retitle.py`
- [x] 1.7 Add `request_scope` in Job pod CLI commands (`stage_job`, `fix-plan`)
  - Verification: `$ uv run pytest tests/commands/test_roadmap_step_fix_plan.py`

## 2. Documents

- [x] 2.1 Update `docs/roadmap/job-success.md` and spec `openspec/specs/roadmap-service-logs/spec.md`
  - Verification: `$ uv run devops docs check`
