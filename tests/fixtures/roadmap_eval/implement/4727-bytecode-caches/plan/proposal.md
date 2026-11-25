# Proposal

## Why

`setup-toolchain` runs `uv sync --compile-bytecode`, and the compile took 7.6 to 14.7 s per job (mean 11.4 s, 10 logs). The xdist workers of a test job import most modules and compile them anyway (#4727).

## What Changes

- `setup-toolchain` takes a `compile-bytecode` input, true by default.
- `test-shard`, `changed-tests`, `job-time` and the Service Image Tests pass `false`.
- The Service Image Tests already restore no tooling cache, so no other input changes.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ci-job-time`: The test jobs skip the bytecode compile.

## Impact

- Workflow: `.github/actions/setup-toolchain/action.yml`, `.github/workflows/ci.yml`, `.github/workflows/service-image-test.yml`
- Tests: `tests/invariants/test_workflow_contracts.py`

## Feasibility

- `uv sync` compiles only on request.
- The input changes one step.
- Verification commands: `uv run devops ci test tests/invariants/test_workflow_contracts.py` and `uv run devops ci --check --only lint,format,typecheck`.

## Existing Tool Considered

uv already gives the switch. No new tool.
