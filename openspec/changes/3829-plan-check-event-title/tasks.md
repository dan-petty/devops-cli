# Tasks

## 1. Cancel the stale plan-check run

Reads: `.github/workflows/pr-title.yml`. Changes: the same file and `tests/invariants/test_workflow_contracts.py`.

- [ ] 1.1 Add the job-level concurrency group `${{ github.workflow }}-${{ github.event.pull_request.number }}` with `cancel-in-progress: true` to `plan-check`.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py -k plan_check` passes
- [ ] 1.2 Add the contract test that reads the group and the cancellation.
  - Verification: the same test command passes
