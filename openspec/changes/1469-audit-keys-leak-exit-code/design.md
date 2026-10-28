# Design

## Context

See proposal.md for the background. `audit_keys_cmd` in `src/devops_cli/commands/config.py` computes `is_overall_compliant` from the plaintext leaks and the unaudited files. It exits 1 only for an unaudited file.

## Goals / Non-Goals

**Goals:**
- Make the exit code of `devops config audit-keys` the gate: 0 only when the audit is compliant.
- Keep the full report in each output format before the exit.

**Non-Goals:**
- Change how the audit finds a plaintext secret or an unaudited file.
- Change the message of a config file that does not parse, which #1468 changes in `src/devops_cli/config/settings.py`.
- Add an option that forces exit 0.

## Decisions

### 1. Exit on the overall compliance, not on each cause
- Decision: Each output branch raises `typer.Exit(1)` when `is_overall_compliant` is false.
- Rationale: The report already computes `is_compliant` from the leaks and the unaudited files. One exit on that value keeps the exit code and the report in agreement. A future cause of non-compliance then also sets the exit code.
- Alternative considered: Add a second `if plaintext_leaks: raise typer.Exit(1)` next to the existing `if unaudited_files` exit.
  - Rejected: Two exits on two causes can disagree with `is_compliant`. That disagreement is the defect of #1469.

### 2. Exit code 1, not the exit code of `InsecureConfigError`
- Decision: A leak exits 1, as an unaudited file does.
- Rationale: The owner decided that a confirmed leak fails the audit, and #1469 asks for exit 1. A CI step or a pre-commit hook reads any non-zero exit as a failure. One exit code for every failed audit is the simple contract.
- Alternative considered: Raise `InsecureConfigError` (`E_INSECURE_CONFIG`, exit code 126) from `src/devops_cli/exceptions/security.py`.
  - Rejected: A shell uses exit code 126 for "found but cannot execute". The error would also print a second error line after the report, and an unaudited file would still exit 1. Two exit codes for one failed gate make a hook check two values.

### 3. Print the full report before the exit
- Decision: The serialized branch emits the report, then exits 1. The table branch prints the table and the security alert, then exits 1.
- Rationale: A CI log and an MCP tool error then hold the keys and the leak to fix. The MCP runner keeps the output of a failed command in its `ToolError`.
- Alternative considered: Exit before the report is printed.
  - Rejected: A failed gate with no report leaves the reader with no next step.

## Risks / Trade-offs

- [A script ran `devops config audit-keys` and read only the output] -> The output does not change. Only the exit code changes, and only for a leak.
- [The MCP tool `config_audit_keys` now returns a tool error for a leak] -> The error holds the full masked report, as it already does for an unaudited file.
