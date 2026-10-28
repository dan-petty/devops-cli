# Proposal

## Why

Issue #2106: the agent tool `scan_uv_audit` in `src/devops_cli/ai/tools/builtin_tools.py` and the MCP tool `scan_uv_audit` in `src/devops_cli/ai/mcp/server.py` run a command line of their own. No adapter in `src/devops_cli/security/` runs uv audit.

- For a `requirements_file`, the tool runs `uv pip audit -r <file>`. uv has no `uv pip audit` subcommand, so this path always fails.
- Without a `requirements_file`, the tool runs `uv audit` and replies with its text output, or with "No known security vulnerabilities identified by uv audit." when the output is empty. The tool does not read the exit code, so a missing uv or an audit that could not run reads as a clean audit. #1435 removed this defect from the other agent scan tools, and left `scan_uv_audit` for this change.
- `uv audit` without `--frozen` locks the project again before the audit, and rewrites a stale `uv.lock`. The MCP tool is marked `readOnlyHint`.

## What Changes

- A new adapter, `devops_cli.security.uv_audit`, holds `UvAuditScanner` and `run_uv_audit_scan`. It starts `uv audit --frozen --quiet --output-format json` in the scanned directory through the `ToolExecutor` of `BaseSecurityScanner`, with an empty standard input, and gives a `ScanOutcome`. `build_uv_audit_cmd` in `config/commands.py` builds this command.
- The adapter reads the JSON report of uv. Each vulnerability is a finding at `uv.lock:<package>`, with the advisory id and the summary in its title, its link as a reference, and the releases that fix it. Each adverse project status (archived, deprecated or quarantined) is a finding too. uv gives no severity, so each finding has the default severity of the finding model, `MEDIUM`.
- A run that writes no report, such as a project with no `uv.lock` or an advisory service that cannot be reached, is a `failed` scan, with what uv wrote on stderr as the reason. A report with no `vulnerabilities` list or no `adverse_statuses` list is a `failed` scan too, and does not read as a clean scan.
- `scan_uv_audit` and the MCP tool `scan_uv_audit` take only `directory`, run the adapter through `_run_adapter_scan`, and reply as the other agent scan tools reply, with the scanner named `uv audit`.
- The `requirements_file` parameter, the `uv pip audit` command line, the clean fallback message and the helper `_run_workspace_security_scan`, which only `scan_uv_audit` used, go.
- `docs/MCP_TOOLS.md` gives the new description and parameters of the MCP tool.
- The reply of the agent tool and the input schema of the MCP tool are observable, so the change carries spec deltas for `scanner-adapters` and `agent-scan-tools`.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `scanner-adapters`: adds how the uv audit adapter starts uv and reads its report.
- `agent-scan-tools`: adds how `scan_uv_audit` runs the uv audit adapter.

## Impact

- Code: `src/devops_cli/security/uv_audit.py` (new), `src/devops_cli/config/commands.py`, `src/devops_cli/ai/tools/builtin_tools.py` and `src/devops_cli/ai/mcp/server.py`.
- Tests: `tests/test_security_uv_audit.py` (new), `tests/test_builtin_tools.py`, `tests/test_mcp.py`, `tests/test_command_builders.py`, the recorded run in `tests/fixtures/scanner_runs/runs_with_findings.json`, and the docstring of `tests/support/fakes/scanners.py`.
- Documentation: `docs/MCP_TOOLS.md`.

## Feasibility

- uv 0.12.23, the uv of this devcontainer: `uv pip audit` gives `error: unrecognized subcommand 'audit'`. `uv audit --help` gives `--output-format <OUTPUT_FORMAT>` with the values `text`, `json` and `sarif`, `--frozen` ("Audit the requirements without locking the project") and `--script` for a PEP 723 script. It gives no option for a requirements file.
- uv 0.13.6, the uv that the `Dockerfile`, `.devcontainer/Dockerfile` and the setup-toolchain action pin, read from the source at the tag `0.13.6`: `PipCommand` in `crates/uv-cli/src/lib.rs` has no `Audit` variant. `AuditArgs` has `frozen` and `output_format`. `crates/uv-audit-operations/src/json.rs` is the same file at `0.13.6` and on `main`. Its `ReportBody` always writes `summary`, `vulnerabilities` and `adverse_statuses`, also when a list is empty, and `ToolReports`, the report for tools, has a `tools` list in their place. `AuditResults::exit_status` in `crates/uv-audit-operations/src/lib.rs` fails only for a vulnerability, and not for an adverse status.
- Command output, uv 0.12.23, on a scratch project: on this repository, `uv audit --frozen --quiet --output-format json` exited 0 with a report of 233 packages and no finding. On a project that pins idna 3.6, it exited 1 with four vulnerabilities and an empty stderr; this run is the recording in `runs_with_findings.json`. Each vulnerability has `dependency.name`, `dependency.version`, `id`, `display_id`, `aliases`, `summary`, `description`, `link` and `fix_versions`, and no severity. `summary` was `null` for the two `PYSEC` advisories.
- Command output, uv 0.12.23: `uv audit --output-format json` on a project whose `pyproject.toml` no longer agreed with its `uv.lock` rewrote the lockfile (its SHA-256 changed). With `--frozen`, the lockfile did not change.
- Command output, uv 0.12.23: with no `uv.lock`, `uv audit --frozen --output-format json` exited 1 with no stdout, and wrote two preview warnings (about 270 characters) before the error on stderr. `ScanOutcome` cuts its reason at `CONST_MAX_ERROR_DETAIL_LENGTH`, 256 characters, so the reason held only the warnings. With `--quiet`, stderr held only the error, and the JSON report was still written. With an advisory service that refused the connection, uv exited 2 with no stdout and "error: Request failed after 3 retries".
- `BaseSecurityScanner` reads a run with no JSON on stdout and a non-zero exit code as `failed`, and a JSON report with findings as `ran` (`_handle_non_json_output`, `_handle_json_output` in `src/devops_cli/security/base.py`). Thus exit code 1 with no report is a failure, and is not read as a finding.
- `devops ci fail-to-pass --base origin/main`, on `origin/main` at `d739a472`: the new tests failed. The agent and MCP tools started a real `uv audit` outside the tool executor, which the test floor refused, `build_uv_audit_cmd` returned `["uv", "audit"]`, and the test module of the adapter did not import.

## Existing Tool Considered

uv audit is the open, maintained tool: it is a subcommand of uv, which the project already uses, and it queries OSV, the database that osv-scanner and `scan_osv` use. `BaseSecurityScanner` and the `ToolExecutor` seam start it, and Pydantic, a dependency of the project, reads its JSON report. The new code is the adapter, about 90 lines: the report models, the text of each finding and the command. It builds no runner and no client of OSV.

pip-audit also audits a requirements file, but it is not in `tools.lock`, and `uvx pip-audit` fetches it from PyPI each time it runs. The issue asks for uv audit, which the `audit` check of `devops ci` already runs.

The change deletes the `uv pip audit` command line, the `uv audit` command line and the fallback message of `scan_uv_audit`, its `requirements_file` parameter in the agent tool and in the MCP tool, the helper `_run_workspace_security_scan`, and the `scan_uv_audit` lines of `test_devops_subcommand_wrappers`, which patched `_run_tool_cmd`.
