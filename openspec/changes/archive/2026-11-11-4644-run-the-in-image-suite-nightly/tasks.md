# Tasks

## 1. Behavior

- [x] 1.1 Write failing tests: the #1643 invariant reads `service-image-test.yml`, requires the schedule, the manual run and the image inputs, and refuses a run for a change to `src/` only; `ci.yml` has no `service-image-test` job
  - Verification: `$ uv run devops ci test tests/invariants/test_architectural_invariants.py tests/commands/test_ci.py`
- [x] 1.2 Move the job to `.github/workflows/service-image-test.yml` with the `paths`, `schedule` and `workflow_dispatch` triggers, and remove the plan-only step filter
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## 2. Documents

- [x] 2.1 State the new triggers in `docs/SDLC.md`
  - Verification: `$ uv run devops ci docs`
