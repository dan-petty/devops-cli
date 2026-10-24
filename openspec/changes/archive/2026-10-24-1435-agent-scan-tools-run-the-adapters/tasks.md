# Tasks

## 1. The agent scan tools run the scanner adapters and report each outcome

- [x] 1.1 Write `test_an_agent_scan_tool_whose_scanner_is_not_installed_says_so_and_not_clean`, `test_an_agent_scan_tool_whose_scanner_fails_with_no_output_says_failed_and_not_clean`, `test_an_agent_scan_tool_whose_scanner_finds_nothing_says_ok_and_no_findings`, `test_an_agent_scan_tool_leads_with_the_status_and_lists_each_finding_masked` and `test_an_agent_scan_tool_cuts_a_long_reply_at_the_tool_output_limit` in `tests/test_builtin_tools.py`, and change the five tests of the agent Semgrep tool to the command and the reply of the adapter. Verify that `uv run devops ci test tests/test_builtin_tools.py` fails on the base
- [x] 1.2 Make `scan_trivy`, `scan_kubelinter`, `scan_pluto`, `scan_bandit`, `scan_gitleaks` and `scan_semgrep` call their adapters through `_run_adapter_scan`, add `_scan_reply`, `_truncated`, `CONST_AGENT_SCAN_STATUS_WORDS`, `CONST_SCAN_NO_RESULT_STATUSES` and the reply messages of `ToolMessages`, and verify that `uv run devops ci test tests/test_builtin_tools.py` passes
- [x] 1.3 Delete the six command lines, the `missing_tool_name` text check, the `cwd` parameter of `_run_tool_cmd`, the message `no_trivy_flaws`, `test_native_security_tool_invocations` and the old command lines in `test_devops_subcommand_wrappers` and `test_builtin_security_and_iac_tools`, and verify that `uv run devops ci test tests/test_builtin_tools.py tests/test_review_security_tools.py` passes

## 2. The scan commands report a scan that gave no result as not run

- [x] 2.1 Write `test_scan_secrets_without_gitleaks_says_it_did_not_run_and_not_that_it_passed` in `tests/test_security_gitleaks.py`, and verify that `uv run devops ci test tests/test_security_gitleaks.py` fails on the base
- [x] 2.2 Make `_handle_single_scanner_result` in `src/devops_cli/commands/scan.py` read `CONST_SCAN_NO_RESULT_STATUSES`, and verify that `uv run devops ci test src/devops_cli/commands/scan.py src/devops_cli/ai/tools/builtin_tools.py` passes

## 3. The MCP Semgrep tool uses the default ruleset unless the caller names one

- [x] 3.1 Write `test_the_mcp_semgrep_tool_scans_with_the_default_ruleset_unless_the_caller_names_one` in `tests/test_mcp.py`, which holds the behavior that #997 delivered, and verify that `uv run devops ci test tests/test_mcp.py` passes

## 4. Checks and documentation

- [x] 4.1 Verify that `uv run ruff check`, `uv run ruff format --check` and `uv run mypy src/devops_cli/ai/tools/builtin_tools.py src/devops_cli/commands/scan.py src/devops_cli/config/constants.py src/devops_cli/lang/en/messages.py` pass, regenerate the docs with `uv run devops docs generate --sync-readme`, and verify that `uv run devops docs check` and `uv run devops openspec check` pass

## Workflow follow-up

- `scan_popeye` runs `PopeyeScanner` and replies with its outcome, after #1434 gives the adapter `-l warn`, the namespace and a parser for the JSON of Popeye 0.22: moved to #1434.
- `scan_uv_audit` and the MCP tool `scan_uv_audit` run a uv audit adapter in `devops_cli.security` (`uv audit --output-format json`) and reply with its outcome, and the `uv pip audit` command, which uv 0.12.23 does not have, goes: moved to #2106.
- The JSON and YAML output of `devops scan trivy|sast|secrets`, which the MCP tools give for `output_format: json`, holds the status and the reason of the scan next to the findings, so a scan that gave no result does not read as `[]`: moved to #2107.
- Pending a person: review the diff in tuicr (tuicr -r origin/main..HEAD).
