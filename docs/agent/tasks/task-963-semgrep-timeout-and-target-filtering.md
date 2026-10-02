# Task: Semgrep AST Scanner Timeout Realignment & Target Filtering (#963)

**Issue**: [#963](https://github.com/dan-petty/devops-cli/issues/963)
**Status**: Done
**Milestone**: v0.2.25
**Priority**: priority/p1-high
**Scope**: scope/security, scope/review

## Description
During `devops ai review branch --persona devsecops release/v0.2.25`, the static security analyzer stage reported:
`! Failed during execution: Semgrep`

### Root Cause Diagnosis
1. **Timeout Parameter Disparity**: `BaseSecurityScanner.scan` defaulted to `DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS` (30.0s), an intentionally short timeout designed for lightweight MCP tools. When running external AST pattern scanning via `Semgrep` across a git branch diff or repository changeset containing hundreds of files, Semgrep took ~70–105 seconds to parse ASTs and execute rulesets (`p/default`), triggering a `subprocess.TimeoutExpired` exception after 30 seconds that was recorded as an analyzer execution failure.
2. **Unfiltered Target List**: In `_scan_gitleaks_and_semgrep`, `all_resolved` paths (including documentation markdown files, massive lockfiles like `uv.lock`, and binary assets) were passed directly to `SemgrepScanner`. Because Semgrep parses code ASTs and IaC grammars, passing non-code files forced Semgrep to open, inspect, and discard dozens of irrelevant files, substantially increasing scanning duration.
3. **Subprocess Working Directory Resolution**: `_resolve_cwd` selected `target_path[0].parent` when passed a list of files across multiple repository directories. When the first diff file was located in `.github/`, Semgrep's working directory was locked to `.github/` rather than the repository root or common ancestor directory.

## Key Changes
1. **Config Defaults & Constants**:
   - Defined `DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS = 300.0` (5 minutes) and `DEFAULT_SEMGREP_TIMEOUT_SECONDS = 300.0` in `src/devops_cli/config/defaults.py` for external security and static analysis CLI scanners.
   - Defined `CONST_LOCKFILE_EXTENSIONS = frozenset({".lock", ".lockb"})` and `CONST_SEMGREP_EXCLUDED_EXTENSIONS = CONST_DOC_EXTENSIONS | CONST_BINARY_EXTENSIONS | CONST_LOCKFILE_EXTENSIONS` in `src/devops_cli/config/constants.py`.
   - Re-exported constants in `src/devops_cli/config/__init__.py`.
2. **Base Security Scanner Hardening**:
   - Realigned `BaseSecurityScanner.scan` default timeout from `DEFAULT_MCP_TOOL_FAST_TIMEOUT_SECONDS` (30s) to `DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS` (300s).
   - Realigned `_resolve_cwd` for file lists using `os.path.commonpath` to safely resolve the common repository or directory root.
3. **Semgrep Target Filtering**:
   - Updated `_build_scan_command` in `src/devops_cli/security/semgrep.py` to filter out documentation, lockfile, and binary extensions before passing file lists to Semgrep CLI.
   - Updated `run_semgrep_scan` to accept `timeout: float = DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS`.
4. **Verification & Tests**:
   - Added unit test specifications verifying Semgrep scannable target filtering, scanner timeout alignment, and common path resolution.

## Acceptance Criteria
- [x] `DEFAULT_SECURITY_SCANNER_TIMEOUT_SECONDS` is defined and used by `BaseSecurityScanner.scan`.
- [x] `CONST_SEMGREP_EXCLUDED_EXTENSIONS` excludes documentation, lockfiles, and binaries from Semgrep AST scans.
- [x] `BaseSecurityScanner._resolve_cwd` computes common ancestor path when given a list of target paths.
- [x] Unit tests in `tests/test_consolidation_security_scanner_base.py` and `tests/test_security_semgrep.py` pass.
- [x] `uv run devops ci` passes all 10 quality gates.
