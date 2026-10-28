# Proposal

## Why

Issue #1469: `devops config audit-keys` finds a plaintext secret in a config file, reports it (`is_compliant: false`, the key under `plaintext_leaks`), and exits 0. A config file that the audit cannot read or parse makes it exit 1 (#1022). Thus a CI step or a pre-commit hook fails on a broken file, but passes on a confirmed plaintext secret. The owner decided that a confirmed leak fails the audit.

## What Changes

- In `src/devops_cli/commands/config.py`, `audit_keys_cmd` exits 1 when the audit is not compliant: when it finds a plaintext secret, or when it cannot read or parse a config file. This applies to the table output and to every serialized output (`--json`, `--format json|yaml|markdown`). The serialized report is printed in full before the exit.
- The table output prints the security alert, then exits 1. It prints the success line only when the audit is compliant.
- The command help, which is the docstring of `audit_keys_cmd`, states the exit codes. `devops docs generate --sync-readme` writes the same text into `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/config.md` and `docs/MCP_TOOLS.md`.
- The MCP tool `config_audit_keys` runs the command, so it reports a leak as a tool error that holds the full report. It already does this for a file that the audit cannot parse.
- `tests/test_config_audit_keys.py` pins exit 1 for a leak, with and without `--json`. The test that pinned exit 0 for a leak is replaced.
- The exit code is observable, so the change has a spec delta for the `config-commands` capability.
- This change fits in one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `config-commands`: adds the requirement that `devops config audit-keys` exits 0 only on a compliant audit, and exits 1 on a plaintext secret or on a config file that it cannot audit.

## Impact

- `src/devops_cli/commands/config.py`: `audit_keys_cmd` exits 1 on a plaintext secret, in each output format; its docstring states the exit codes.
- `tests/test_config_audit_keys.py`: two tests for a leak, one for the table output and one for the `--json` output. Each expects exit 1, and the table test expects no success line.
- Generated documents: `README.md`, `docs/CLI_REFERENCE.md`, `docs/commands/config.md`, `docs/MCP_TOOLS.md`.

## Feasibility

- Confirmed against the source at `origin/main` (bb46660c): `audit_keys_cmd` computes `is_overall_compliant = not plaintext_leaks and not unaudited_files`. It raises `typer.Exit(1)` only `if unaudited_files`, in the serialized branch and in the table branch. A leak alone reaches `return`, or the end of the function, with exit 0.
- Confirmed with command output on devops-cli 0.8.2: a config file that holds `grafana.token: FAKE-1469-plaintext-token`, named by `DEVOPS_CLI_CONFIG`, gives `is_compliant: false` and `plaintext_leaks: ["config.yaml:grafana.token"]`. `devops config audit-keys --json` and `devops config audit-keys` both exit 0.
- `tests/test_config_audit_keys.py::test_config_audit_keys_plaintext_leak_detected` asserts `result.exit_code == 0` for that case.
- The MCP runner `_run_mcp_cmd` in `src/devops_cli/ai/mcp/server.py` raises `ToolError` with the masked output on a non-zero exit. Thus the MCP tool keeps the report in its error.

## Existing Tool Considered

The command sets its exit code with `typer.Exit`, which Typer and Click supply. The command already uses it for a file that it cannot audit. No other tool covers the exit code of a devops-cli command. The change deletes the branch that let a leak exit 0, and the second `typer.Exit(1)` call that the serialized branch and the table branch each had for an unaudited file. Each branch now has one exit on the overall compliance.
