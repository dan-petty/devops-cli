# Proposal

## Why

Issue #1435: the agent scan tools in `devops_cli.ai.tools.builtin_tools` reported a missing or failed scan as a clean scan. `_run_tool_cmd` returned the standard output of the scanner, or a fallback message when the output was empty, and did not read the exit code. `run_subprocess` reports a missing program as exit code 127 with no output. Thus `scan_trivy`, `scan_kubelinter`, `scan_pluto`, `scan_bandit`, `scan_gitleaks` and `scan_semgrep` replied "No ... detected" when no scan ran or when the scanner failed. The check for the text `No such file or directory: '<tool>'` did not match, because `run_subprocess` does not raise for a missing program. Each tool also kept its own command line next to the scanner adapters of `devops_cli.security`, and two of them read human output. A model that verifies a CVE reads these replies.

`devops scan secrets`, which the MCP tool `scan_secrets` runs, had the same defect for a missing Gitleaks. The Gitleaks adapter gives that outcome the status `not installed`, and the command printed that the scan found no secrets.

## What Changes

- `scan_trivy`, `scan_kubelinter`, `scan_pluto`, `scan_bandit`, `scan_gitleaks` and `scan_semgrep` call `run_trivy_scan`, `run_kubelinter_scan`, `run_pluto_scan`, `run_bandit_scan`, `run_gitleaks_scan` and `run_semgrep_scan` over the workspace path. Each scanner thus starts through the `ToolExecutor` of its adapter, with an empty standard input (#1079), and the scan of an agent tool is the scan of `devops scan`.
- The reply gives the status of the `ScanOutcome` first: `ok` for a scan that ran, `not installed`, `failed`, `not_applicable`, or the name of any other status, such as `coverage_gap`. A line with the reason follows when the outcome has one. A scan that gave no result then says so, and tells the model not to report the target as clean. A scan that ran lists its findings, or says that it has none. The tool masks the whole reply with `mask_secrets`, then cuts it at `DEFAULT_TOOL_DIFF_MAX_CHARS`, as before.
- `scan_semgrep` takes the cached-ruleset behavior of the adapter. With no cached registry ruleset, it runs the rule pack alone and replies `coverage_gap` with the fetch command.
- The command lines of the six tools, the `missing_tool_name` text check, the `cwd` parameter of `_run_tool_cmd` and the unused message `no_trivy_flaws` go.
- `CONST_SCAN_NO_RESULT_STATUSES` holds the statuses of a scan that gave no result. The agent tools and `devops scan trivy|sast|secrets` read it, so these commands report a Gitleaks that is not installed as not run.
- The MCP tool `scan_sast` runs `devops scan sast`, whose `--config` default is `DEFAULT_SEMGREP_CONFIG`, since #997 generated the MCP tools from the CLI. A test now holds this.
- The replies of the agent tools and the output of `devops scan secrets` are observable, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

- `agent-scan-tools`: how the scan tools that devops-cli gives to its agents and MCP clients run the scanner adapters and report each scan outcome.

### Modified Capabilities

None.

## Impact

- Code: `src/devops_cli/ai/tools/builtin_tools.py`, `src/devops_cli/commands/scan.py`, `src/devops_cli/config/constants.py` and `src/devops_cli/lang/en/messages.py`.
- Tests: `tests/test_builtin_tools.py`, `tests/test_security_gitleaks.py` and `tests/test_mcp.py`. `test_native_security_tool_invocations` in `tests/test_review_security_tools.py` goes.
- `scan_popeye` and `scan_uv_audit` do not change. The Feasibility section gives the reason.

## Feasibility

- On main at 1b257714, `_run_tool_cmd` (`src/devops_cli/ai/tools/builtin_tools.py:42-78`) returned `output or fallback_msg` and did not read `returncode`. `run_subprocess` (`src/devops_cli/core/process.py:400-418`) catches `FileNotFoundError` and returns exit code 127 with no output. `_run_workspace_security_scan` (`:250-272`) looked for `No such file or directory: '<tool>'`, which no reply holds.
- On that base, the new tests failed (20 failed). A tool whose scanner was not on PATH started it, and the test floor refused the process. A scanner that exited 2 with no output gave the clean fallback message. A Trivy report came back as raw JSON with an unmasked GitHub token. `devops scan secrets` with no Gitleaks on PATH printed `✓ No secrets or credential leaks detected.`
- Each of the six tools has an adapter that takes a workspace path: `run_trivy_scan(target)`, `run_kubelinter_scan(target)`, `run_pluto_scan(target)`, `run_bandit_scan(target)`, `run_gitleaks_scan(target)` and `run_semgrep_scan(target, config=...)`. Each one starts its tool through `BaseSecurityScanner._run_tool`, which builds a `ToolRequest`. The defaults of the adapters match the old command lines: Trivy `fs` with every severity, Bandit at `medium` (the old `-ll`), and Gitleaks `detect --no-git --source`.
- The MCP part: `CONST_MCP_EXPOSURE_TABLE` generates `scan_sast`, `scan_secrets` and `scan_trivy` from `devops scan sast|secrets|trivy`, which call the adapters. `docs/MCP_TOOLS.md` gives `p/default` as the default `config` of `scan_sast`. #997 deleted the `uv run devops scan ...` path with the `auto` default that the issue cites.
- Two tools cannot run an adapter yet, so this change does not change them:
  - `scan_popeye`: `build_popeye_cmd` passes `-s error,warn`, but `-s` is `--sections` in Popeye 0.22.1. `popeye --help` gives `-s, --sections strings  Specify which resources to include in the scan`, and the level flag is `-l, --lint`. `PopeyeScanner` also drops the `namespace` that `run_popeye_scan` takes, and #1434 records that its parser reads `sanitizers`, which Popeye 0.22 does not write. Through the adapter, the agent tool would scan no resource and reply `ok` with no findings. #1434 must fix the adapter first.
  - `scan_uv_audit`: no adapter in `devops_cli.security` runs `uv audit`. Only `devops_cli.core.dependency_audit` reads its exit code, for `devops ci`. Also, `uv pip audit`, which the tool runs for a `requirements_file`, does not exist in uv 0.12.23: `uv pip audit --help` gives `unrecognized subcommand 'audit'`.
- The check of the issue, `rg -n '\["(trivy|semgrep|bandit|gitleaks|kube-linter|popeye)"' src/devops_cli/ai`, prints one line, the `["popeye"]` of `scan_popeye`, until the follow-up for Popeye.

## Existing Tool Considered

The scanner adapters of `devops_cli.security` are the existing tool. Each adapter runs its open-source scanner (Trivy, kube-linter, Pluto, Bandit, Gitleaks or Semgrep) through the `ToolExecutor` seam, and reads its JSON report into a `ScanOutcome`. The change uses them, and builds no new runner or parser. `mask_secrets` of `devops_cli.security.sanitizer` masks the reply. The new code is the text of the reply only, about 40 lines.

The change deletes the six command lines in `builtin_tools.py`, the `missing_tool_name` text check, the `cwd` parameter of `_run_tool_cmd`, the message `no_trivy_flaws`, the test `test_native_security_tool_invocations`, which patched `_run_tool_cmd`, and the parts of `test_devops_subcommand_wrappers` and `test_builtin_security_and_iac_tools` that held the old command lines.
