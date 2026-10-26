# Design

## Skip scanner option

`devops scan report` receives a `--skip` option with alias `--skip-scanner`.
The option accepts repeated flags or comma-separated scanner names.
The command validates that all names in `--skip` are known scanners registered in `global_scanner_registry`.
If an unknown scanner is provided in `--skip`, the command prints an error and exits with code 2.
If both `--scanner` and `--skip` are provided, the command prints an error and exits with code 2.

## Workflow updates

The Static Analysis job in `.github/workflows/ci.yml` has two analysis steps:
1. `Static Analysis Quality Gate`: runs `uv run devops ci --check --no-cache --skip test,outdated`.
2. `Security Scan`: runs `uv run devops scan report --sarif .data/scan.sarif --skip bandit`.

The first step runs the `security` quality gate, which executes Bandit.
The second step runs all security scanners except Bandit to generate SARIF.
Bandit starts once in the Static Analysis job.

## Workflow contract test

The contract test `test_the_static_job_starts_bandit_once` loads `.github/workflows/ci.yml`.
It inspects all steps in the `static` job.
It resolves check rows for `devops ci` invocations using `resolve_step_rows`.
It resolves scanner lists for `devops scan report` invocations using `resolve_scan_report_scanners`.
It asserts that the total number of steps starting Bandit equals 1.
A negative mutation test verifies that omitting `--skip bandit` causes the contract to fail.
