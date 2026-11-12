# Tasks

## 1. Workflows

- [x] 1.1 Add the invariant test that lists the jobs that a push to the release pull request starts, and see it fail on the base with the 7 jobs of this change.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py`
- [x] 1.2 Add the release skip term to the `if` of `service-image`, `runner-image`, `mcp-server-image`, `changed-tests` and `design-tokens` in `ci.yml`, of `devcontainer` in `devcontainer-image.yml`, and of `service-image-test` in `service-image-test.yml`. Update the tests that pin these conditions.
  - Verification: `$ uv run devops ci test tests/invariants/test_workflow_contracts.py tests/invariants/test_runner_image.py tests/commands/test_ci.py tests/commands/test_ci_repeat.py`
- [x] 1.3 Check the workflows.
  - Verification: `$ uv run devops ci --only actionlint,zizmor`

## 2. Documents

- [x] 2.1 Say in `docs/SDLC.md` that the release pull request runs only the checks that the ruleset reads, and extend the status note of ADR 0004.
  - Verification: `$ uv run devops ci docs`
