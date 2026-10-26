# Tasks

## 1. Failing tests

- [x] Add the workflow contract test in `tests/test_workflow_contracts.py` that fails because `ci.yml` currently runs Bandit twice.
- [x] Add unit tests for `devops scan report --skip` in `tests/test_scan_outcomes_and_gating.py`.
  - Verification: `uv run pytest tests/test_workflow_contracts.py -k test_the_static_job_starts_bandit_once` fails.

## 2. Implementation

- [x] Add `skip_scanners` help message to `src/devops_cli/lang/en/help.py`.
- [x] Add `--skip` / `--skip-scanner` support to `scan_report` in `src/devops_cli/commands/scan.py`.
- [x] Implement `resolve_scan_report_scanners` in `src/devops_cli/commands/scan.py`.
- [x] Update `Security Scan` step in `.github/workflows/ci.yml` to pass `--skip bandit`.
- [x] Update `test_ci_workflow_publishes_scanner_sarif_to_code_scanning` in `tests/test_ci.py`.
  - Verification: `uv run pytest tests/test_workflow_contracts.py tests/test_scan_outcomes_and_gating.py tests/test_ci.py` passes.

## 3. Documentation and sync

- [x] Run `uv run devops docs generate --sync-readme` to synchronize command documentation.
- [x] Verify `uv run devops docs check` passes.

## 4. Quality gate and checks

- [x] Run `uv run devops ci fail-to-pass --base origin/main`.
- [x] Run `uv run devops ci` and verify all quality gates pass.
