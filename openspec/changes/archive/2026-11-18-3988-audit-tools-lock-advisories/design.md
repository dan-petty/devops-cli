# Design: #3988

## Context
`devops ci audit` runs `uv audit` and `npm audit`. It omits the Python requirement files in `src/devops_cli/tools_lock/`. Known advisories affect `semgrep.txt` for `mcp` and `opentelemetry-api`. Semgrep upstream pins vulnerable versions.

## Goals
- Add `osv-scanner --lockfile requirements.txt:<file>` to the `audit` check for each Python tool in `src/devops_cli/tools_lock/`.
- Support `.osv-scanner-ignore.yaml` for time-limited ignores of findings with no released fix.
- Fail when a requirement file has unignored advisories or expired ignores.
- Pass when advisories have active ignore entries.

## Decisions
- `build_osv_scanner_audit_cmd(path)` builds `["osv-scanner", "--lockfile", f"requirements.txt:{path}"]`.
- `osv_scanner_lockfile(cmd)` extracts the requirement file path from the command.
- `_tools_lock_audit_cmds()` in `ci.py` generates commands for all tools in `load_tools_lock().python`.
- `_audit_ignores(cmd)` loads `.osv-scanner-ignore.yaml` when auditing with `osv-scanner`.
- `audit_verdict` evaluates `osv-scanner` results: return code 0 is CLEAN, return code 1 with all advisories in `ignored` is CLEAN, return code 1 with unignored advisories is VULNERABLE, other return codes are NOT_RUN.
