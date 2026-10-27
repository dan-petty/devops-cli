# Design

## Context

See proposal.md - Why. `ScanOutcome` in `src/devops_cli/security/base.py` subclasses `list` and holds `status: str` and `reason: str`. When `devops scan` subcommands output in JSON or YAML format, they currently serialize `[f.model_dump() for f in findings]`. If a scanner is not installed or fails, `findings` is empty, emitting `[]`.

## Goals / Non-Goals

**Goals:**
- Emit a dictionary containing `status`, `reason`, and `findings` for JSON and YAML output formats in `devops scan trivy`, `devops scan secrets`, `devops scan sast`, and `devops scan iac`.
- Ensure scans that gave no result do not appear as a clean scan with `[]`.

**Non-Goals:**
- Change the human-readable table output of the scan subcommands.
- Change agent builtin text tool replies in `src/devops_cli/ai/tools/builtin_tools.py`, which already format the status and reason through `_scan_reply`.

## Decisions

### 1. Dictionary structure for serialized scanner outcome

`devops scan` commands that return a `ScanOutcome` serialize:
```python
{
    "status": getattr(findings, "status", "ran") or "ran",
    "reason": getattr(findings, "reason", "") or "",
    "findings": [f.model_dump() for f in findings],
}
```
Rejected alternative: Emit a top-level list with an error object when status is in `CONST_SCAN_NO_RESULT_STATUSES`. Rejected because consumers expect a consistent schema across clean runs, runs with findings, and unrun scans.

Rejected alternative: Raise a CLI exception on unrun scans in JSON mode. Rejected because `devops scan` exits 0 with a warning message in table mode; changing exit codes would break existing callers.

## Risks / Trade-offs

- [Downstream consumers expecting a bare array of findings] → Callers reading JSON must read the `findings` key instead of the root array. This is pre-1.0 alpha software with no backwards compatibility shim.
