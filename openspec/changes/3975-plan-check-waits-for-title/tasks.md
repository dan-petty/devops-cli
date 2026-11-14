# Tasks

## 1. Wait for the title check

Reads: `src/devops_cli/roadmap/plan_check.py`, `.github/workflows/pr-title.yml`. Changes: the same files, `src/devops_cli/lang/en/messages.py`, and the named tests.

- [ ] 1.1 Change the `plan-check` job condition from `always()` to `!cancelled()`.
- [ ] 1.2 Poll the title check for up to 120 seconds at 5-second intervals, and make a pending check at the limit no problem.
- [ ] 1.3 Add `PlanCheckResult.notes` and the note message.
  - Verification: `$ uv run devops ci test tests/roadmap/test_roadmap_plan_check.py tests/invariants/test_workflow_contracts.py` passes
