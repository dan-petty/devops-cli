# Proposal

## Why

The `devops ci` check bound of 1800 s cannot fire in CI, because the job limit includes the setup. A shard test row has no own bound, so a hung teardown waits for the job kill with no line that names the row. The coverage-index build took 1,627 s of its 1,800 s bound once (#4683).

## What Changes

- `CheckSpec` takes an optional `timeout_seconds`, and the test row of a shard run uses 900 s.
- The Service Image Tests wrap `docker run` in `timeout --kill-after=30 900`.
- The coverage-index build uses `DEFAULT_CI_COVERAGE_INDEX_TIMEOUT_SECONDS` of 3600 s, which records the measured time.
- `docs/TESTING.md` says that the row and job bounds, not pytest-timeout, bound a hung teardown.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-gate-rows`: A shard test row has its own bound.
- `ci-service-image-tests`: The suite run has a bound inside the job limit.

## Impact

- Code: `src/devops_cli/commands/ci.py`, `src/devops_cli/config/defaults.py`
- Workflow: `.github/workflows/service-image-test.yml`
- Document: `docs/TESTING.md`
- Tests: `tests/commands/test_ci_shard.py`, `tests/invariants/test_workflow_contracts.py`

## Feasibility

- `CheckSpec` already builds each row, and the runner takes one `timeout`.
- coreutils `timeout` is in the image.
- Verification commands: `uv run devops ci test tests/commands/test_ci_shard.py tests/invariants/test_workflow_contracts.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

coreutils `timeout` and pytest-timeout already exist. The change gives each a bound inside the job limit, as the owner rule says.
