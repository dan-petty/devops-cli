# Proposal

## Why

Issue #2107: `devops scan trivy|sast|secrets` with `--format json` or `yaml` prints only the findings list. A scan that gave no result (`not installed`, `failed`, `not_applicable`) prints `[]`. This empty list reads as a clean scan to an agent or caller that reads JSON output from the commands or their MCP tools.

## What Changes

- `devops scan trivy`, `devops scan sast`, `devops scan secrets` and `devops scan iac` serialize a mapping with `status`, `reason`, and `findings` when the output format is JSON or YAML.
- A scan that gave no result never prints only `[]`. It prints the status and the reason next to an empty findings list.
- The command output is observable, so the change carries a spec delta.
- The change fits one pull request.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `agent-scan-tools`: adds the requirement that JSON and YAML serialization of `devops scan` commands includes `status` and `reason` alongside `findings`.

## Impact

- Code: `src/devops_cli/commands/scan.py`.
- Tests: `tests/test_scan.py`, `tests/test_security_gitleaks.py`, `tests/test_security_semgrep.py`.

## Feasibility

- The premise was confirmed in `src/devops_cli/commands/scan.py:190-193`, `262-265`, `427-430`, and `497-500`. Each subcommand extracts `data = [f.model_dump() for f in findings]` and passes it to `emit_serialized(data, resolved)`. When `findings` has no items, `data` is `[]`, omitting the `status` and `reason` attributes that `ScanOutcome` carries.
- The test `test_scan_secrets_without_gitleaks_says_it_did_not_run_and_not_that_it_passed` in `tests/test_security_gitleaks.py:96-112` confirms that Gitleaks absence produces a warning in table mode. Invoking the same command with `--json` outputs `[]\n`.

## Existing Tool Considered

`ScanOutcome` in `devops_cli.security.base` already holds `status`, `reason`, and `findings`. `emit_serialized` in `devops_cli.output.serialization` serializes standard Python dictionaries to JSON and YAML. No new library or custom serializer is needed; the commands serialize a dictionary containing these existing fields.
