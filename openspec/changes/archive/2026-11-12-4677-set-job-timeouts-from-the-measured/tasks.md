# Tasks

## 1. Contract tests

Kind: test-only edits. Changes: `tests/invariants/test_workflow_contracts.py`.

- [x] 1.1 Add the tests of the job limits, of the step limits of the gate and test steps, of the hang bound of one test under a test step, and of each step limit under its job limit in every workflow. Change the pinned limits of Docs Site Build and Image Pins to 5.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`

## 2. Workflows

Kind: workflows. Changes: `.github/workflows/ci.yml`, `.github/workflows/service-image-test.yml`.

- [x] 2.1 Set the job limits of `ci.yml` and `service-image-test.yml` from the longest runs, and give the gate and test steps their step limits.
  - Verification: `$ uv run devops ci --only actionlint,zizmor`
- [x] 2.2 Run the contract tests on the changed workflows.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py tests/invariants/test_architectural_invariants.py`
