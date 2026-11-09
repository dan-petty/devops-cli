# Proposal: #2440

## Why

The agent tool `scan_uv_audit` and its MCP tool check that their directory is inside the workspace, but uv finds the project from that directory and each parent. When no directory from the named one up to the workspace root holds a project, uv finds a project in a parent of the workspace and audits its `uv.lock`. The reply gives each finding at `uv.lock:<package>` and does not name the lockfile, so an agent reads the packages and versions of a lockfile outside the workspace and takes them as the audit of the workspace. Closes #2440.

## What Changes

- `run_uv_audit_scan` in `src/devops_cli/security/uv_audit.py` resolves the project that uv would audit from the target with `uv workspace dir --project <target>`, and refuses the audit, with `not_applicable` and a reason that names the project, when that project lies outside the workspace.
- The probe runs only when uv is installed, so the `not installed` outcome is unchanged, and it runs before the audit so a wrong project is never audited.
- A message field in `ScanMessages` in `src/devops_cli/lang/en/messages.py` carries the refusal, with the directory of the project.
- `tests/security/test_security_uv_audit.py` and `tests/security/test_builtin_tools.py` hold a case for a project outside the workspace, a case for a project in the workspace, and the `not installed` case.
- `tests/support/fakes/scanners.py` answers the `uv workspace dir` probe of a scanner, without a record in `runs`, since a probe is a read of the target, not a scan.
- The `scanner-adapters` capability gains a requirement for the refusal, because the adapter reports a new outcome to a person.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `scanner-adapters`: uv audit refuses a project outside the workspace

## Impact

- Code: `src/devops_cli/security/uv_audit.py`, `src/devops_cli/lang/en/messages.py`
- Tests: `tests/security/test_security_uv_audit.py`, `tests/security/test_builtin_tools.py`, `tests/support/fakes/scanners.py`
- A scan of a workspace that is a subdirectory of a uv project now gives `not_applicable` instead of the audit of the parent project.

## Feasibility

- The premise holds against the real system. With a uv project at `proj` and an empty `proj/sub`, `uv workspace dir --project proj/sub` writes `proj`, the project that uv would audit, which lies outside a workspace at `proj/sub`. uv 0.13.6 and the devcontainer's uv 0.12.23 both resolve the project this way, and `uv workspace dir` requires a `pyproject.toml`, so it names the project that `uv audit` audits and no other.
- The first check of the implementation is `uv run devops ci test tests/security/test_security_uv_audit.py`, which runs the new refusal and in-workspace cases beside the existing uv audit cases.

## Existing Tool Considered

- `uv workspace dir` (uv 0.12.23+) resolves the project root from a directory and writes it to stdout. It names the project that uv would audit, which is the one the scan must bound. The adapter calls it and checks the result against the workspace. No new library is needed.
