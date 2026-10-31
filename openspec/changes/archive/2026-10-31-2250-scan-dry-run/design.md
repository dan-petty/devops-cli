# Design: Classify Scan Commands and Add Request Plans in Dry Run

## Context

The owner's dry-run rule (#412) states that a dry run makes zero external requests and returns the requests that the real run would make.
Under `devops scan`, 12 commands were unclassified or lacked planned request previews.
Several commands executed subprocesses or made HTTP network requests to OSV during `--dry-run`.
Others printed legacy `CommandDryRunResult` structures that showed only arguments.

## Architecture

```
devops --dry-run scan <command>
       │
       ▼
 ┌───────────────┐
 │ Proxy Handler │
 └──────┬────────┘
        │
        ├─────────────────────────────────────────────────┐
        ▼                                                 ▼
 ┌───────────────────────────┐             ┌─────────────────────────────┐
 │ no-external-request       │             │ request-plan                │
 │ Execute command normally  │             │ Generate PlannedRequest(s) │
 │ (aibom, complexity,       │             │ Render plan with            │
 │  injection, sarif, sbom,  │             │ render_request_plan         │
 │  secrets, workflows)      │             │ (scan, trivy, fix, report,  │
 └───────────────────────────┘             │  sast)                      │
                                           └─────────────────────────────┘
```

## Decisions

### 1. Separate Request Planners into `src/devops_cli/security/scan_plans.py`

Shared builders assemble arguments and `PlannedRequest` instances:
- `plan_trivy_scan`: builds `PlannedRequest` for Aqua Trivy vulnerability scanning.
- `plan_semgrep_scan`: builds `PlannedRequest` for Semgrep SAST scans.
- `plan_scan_report`: builds `PlannedRequest` list for all selected scanners in the registry.
- `plan_scan_fix`: builds `PlannedRequest` list for OSV batch queries, upgrade command, and optional branch creation.

The real execution paths and dry-run paths share identical command line argument builders.
Plans cannot drift from real execution.

### 2. Update Result Models

- `VulnerabilityRemediationResult` gains `dry_run: bool = False` and `requests: list[dict[str, Any]] = Field(default_factory=list)`.
- `ScanReport.as_dict()` records `dry_run: True` and `requests` when executed under dry run.

### 3. Remove Legacy Echo Previews

Remove `CommandDryRunResult` and `--dry-run` options from read-only inspection commands:
- `scan aibom`
- `scan complexity`
- `scan injection`
- `scan sbom`
- `scan secrets`
- `scan workflows`

These commands run locally and safely under `devops --dry-run`.
Echo-only previews are removed without a shim.
