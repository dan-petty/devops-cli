# Proposal: Classify Scan Commands and Add Request Plans in Dry Run

## Why

Issue #2249 classified OpenTofu commands.
Issue #2250 tracks security and vulnerability scan commands.
Five commands execute external tools or network requests: `scan`, `scan trivy`, `scan fix`, `scan report`, and `scan sast`.
Seven commands run local file and AST analyses: `scan aibom`, `scan complexity`, `scan injection`, `scan sarif`, `scan sbom`, `scan secrets`, and `scan workflows`.
Some commands run real scans during dry-run or return echo-only results.

This change delivers issue #2250.
It classifies all 12 scan commands and adds request plans.

## What Changes

1. Decorate scan commands with their dry-run classes:
   - `request-plan`: `scan` (callback), `scan trivy`, `scan fix`, `scan report`, and `scan sast`.
   - `no-external-request`: `scan aibom`, `scan complexity`, `scan injection`, `scan sarif`, `scan sbom`, `scan secrets`, and `scan workflows`.
2. Create `src/devops_cli/security/scan_plans.py` to build ordered `PlannedRequest` sequences.
3. Update `VulnerabilityRemediationResult` and `ScanReport` to record dry-run metadata.
4. Remove echo-only previews and explicit `--dry-run` options from read-only commands without a shim.
5. Remove all 12 scan command paths from `tests/fixtures/dry_run_gaps.json`.
6. Add unit and invariant test coverage to verify dry-run behavior.

This change fits in one pull request.

## Capabilities

- `command-dry-run-class`: Extend capability with requirements for scan request plans and local command execution.

## Impact

- All scan commands obey the dry-run rule.
- External scanner executions, rule downloads, and network lookups do not occur in dry run.
- Operators inspect planned commands and arguments before execution.

## Feasibility

We confirmed the behavior of all 12 commands in `src/devops_cli/commands/scan.py`.
Commands that execute Trivy, Semgrep, OSV lookups, or batch scanner suites are confirmed.
The dry run proxy and `PlannedRequest` architecture support command execution plans.

## Existing Tool Considered

We considered Typer native dry-run support, but Typer does not generate request plans.
`devops_cli.dry_run.requests.PlannedRequest` is the established repository standard.
We delete legacy echo-only logic without adding external dependencies.
