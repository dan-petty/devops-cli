# Proposal

## Why

Issue #1746: the Static Analysis CI job runs Bandit twice on every push.
It runs Bandit once in `devops ci --skip test,outdated` and again in `devops scan report`.
Running Bandit twice wastes approximately 42 seconds of runner time during each job run.

## What Changes

- Add `--skip` (with alias `--skip-scanner`) to `devops scan report` to allow skipping specific scanners.
- Update the `Security Scan` step in `.github/workflows/ci.yml` to pass `--skip bandit`.
- Add a workflow contract test in `tests/test_workflow_contracts.py` ensuring that the Static Analysis job starts Bandit once.
- Update existing CI parity and code scanning SARIF tests in `tests/test_ci.py` to match the updated step command.
- Add unit tests for `devops scan report --skip` in `tests/test_scan_outcomes_and_gating.py`.
- Synchronize documentation with `devops docs generate --sync-readme`.
- This change sets `skip_specs: true` in `.openspec.yaml`.

## Capabilities

### New Capabilities

- `devops scan report` accepts `--skip` / `--skip-scanner` to omit specified scanners from the report run.

### Modified Capabilities

None.

## Impact

- CLI: `src/devops_cli/commands/scan.py`
- Help texts: `src/devops_cli/lang/en/help.py`
- Workflow: `.github/workflows/ci.yml`
- Documentation: `docs/commands/scan.md`, `README.md`
- Tests: `tests/test_workflow_contracts.py`, `tests/test_ci.py`, `tests/test_scan_outcomes_and_gating.py`

## Feasibility

- Bandit execution over `src/` and `tests/` takes approximately 42 seconds when executed.
- The `Static Analysis Quality Gate` step in `.github/workflows/ci.yml` covers the `security` check row.
- The `security` check row executes Bandit with the `.bandit` configuration file at medium severity threshold.
- Skipping Bandit in `devops scan report` stops the second run and reduces the Static Analysis job duration.
- The workflow contract reads `.github/workflows/ci.yml` and verifies that the `static` job starts Bandit once across its steps.

## Existing Tool Considered

`devops scan report` currently supports `--scanner` to include named scanners.
Adding `--skip` mirrors the `--skip` option of `devops ci` and reuses existing scanner registry mechanisms.
No third-party tool is needed to filter scanners.
