# Tasks: #3988

## 1. Commands and Core
- [x] 1.1 Add `build_osv_scanner_audit_cmd` and `osv_scanner_lockfile` in `src/devops_cli/config/commands.py`.
- [x] 1.2 Add `CONST_OSV_SCANNER_IGNORE_FILE` in `src/devops_cli/config/constants.py`.
- [x] 1.3 Add `_read_osv_failure` and `osv_advisory_ids` in `src/devops_cli/core/dependency_audit.py`.
- [x] 1.4 Wire `_tools_lock_audit_cmds` and `.osv-scanner-ignore.yaml` into `src/devops_cli/commands/ci.py`.

## 2. Ignores Configuration
- [x] 2.1 Add `.osv-scanner-ignore.yaml` with active ignore entries for `mcp` and `opentelemetry-api` in `semgrep.txt`.

## 3. Tests and Verification
- [x] 3.1 Add unit tests for `osv_scanner_lockfile`, `audit_verdict` with `osv-scanner`, and ignore evaluation.
- [x] 3.2 Update CI audit command and gate tests in `tests/commands/test_ci.py` and `tests/commands/test_ci_maintain.py`.
- [x] 3.3 Verify fail-to-pass and run pre-commit checks.
