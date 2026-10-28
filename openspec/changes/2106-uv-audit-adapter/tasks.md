# Tasks

## 1. The uv audit adapter

- [x] Add failing tests in `tests/test_security_uv_audit.py`: the adapter starts `uv audit --frozen --quiet --output-format json` in the project directory and reads each vulnerability and adverse status as a finding, a report with no finding is a clean scan, a run with no lockfile is a failed scan with the error of uv, and a report of another layout is a failed scan. Change the expected `build_uv_audit_cmd` in `tests/test_command_builders.py`
  - Verification: `uv run devops ci test tests/test_security_uv_audit.py tests/test_command_builders.py` fails on `origin/main`
- [x] Add `src/devops_cli/security/uv_audit.py` with `UvAuditScanner`, `parse_uv_audit_json` and `run_uv_audit_scan`, and make `build_uv_audit_cmd` return the audit command with `--frozen`, `--quiet` and `--output-format json`
  - Verification: `uv run devops ci test tests/test_security_uv_audit.py tests/test_command_builders.py`

## 2. The agent and MCP tools run the adapter

- [x] Record a run of uv audit with findings in `tests/fixtures/scanner_runs/runs_with_findings.json` and name it in the docstring of `tests/support/fakes/scanners.py`. Add failing tests: `test_the_agent_uv_audit_tool_runs_the_uv_audit_adapter_over_the_directory` and the `uv-audit` cases of the not-installed and failed-scan tests in `tests/test_builtin_tools.py`, and `test_the_mcp_uv_audit_tool_takes_a_directory_and_runs_the_uv_audit_adapter_there` in `tests/test_mcp.py`
  - Verification: `uv run devops ci test tests/test_builtin_tools.py tests/test_mcp.py` fails on `origin/main`
- [x] Make `scan_uv_audit` call `run_uv_audit_scan` through `_run_adapter_scan`, and make the MCP tool `scan_uv_audit` take only `directory`. Delete the `requirements_file` parameter, the `uv pip audit` and `uv audit` command lines, the fallback message, `_run_workspace_security_scan` and the `scan_uv_audit` lines of `test_devops_subcommand_wrappers`
  - Verification: `uv run devops ci test tests/test_builtin_tools.py tests/test_mcp.py`
- [x] Regenerate `docs/MCP_TOOLS.md`
  - Verification: `uv run devops docs generate --sync-readme` and `uv run devops docs check`

## 3. Archive

- [ ] Archive the change
  - Verification: `uv run devops openspec archive 2106-uv-audit-adapter`
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
