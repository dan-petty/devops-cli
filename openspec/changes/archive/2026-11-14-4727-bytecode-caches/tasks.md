# Tasks

## 1. Skip the sync compile in the test jobs

Reads: `.github/actions/setup-toolchain/action.yml`. Changes: the action, `ci.yml`, `service-image-test.yml`, and the workflow test.

- [x] 1.1 Add the input and the conditional sync.
- [x] 1.2 Pass `false` in the four test jobs.
- [x] 1.3 Add the contract test.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py` passes
