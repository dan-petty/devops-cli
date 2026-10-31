# Design: Classify OpenTofu Commands and Add Request Plans in Dry Run

## Architecture

This change integrates OpenTofu commands into the dry-run classification system.
Each command receives either the `request-plan` or `no-external-request` classification.

### Request-Plan Commands

Nine commands execute external operations:
`tf init`, `tf plan`, `tf apply`, `tf destroy`, `tf output`, `tf deploy-cloud`, `tf lint`, `tf cost breakdown`, and `tf cost diff`.

In dry-run mode:
- The command makes no external process call or network request.
- The command returns its result type marked with `dry_run=True` and the ordered `PlannedRequest` items.
- In table format, `render_request_plan` prints the numbered commands.
- The plan builders in `src/devops_cli/tf/tf_plans.py` share argument builders with the command execution paths.

### No-External-Request Commands

Six commands operate strictly on local files:
`tf drift`, `tf fmt`, `tf graph`, `tf notify-plan`, `tf status`, and `tf validate`.

In dry-run mode:
- The proxy executes the command normally under `devops --dry-run <command>`.
- Echo-only previews and explicit `--dry-run` options are removed from read-only commands without a shim.
- No external network or provider call is made.

### Gaps List and Invariants

All 15 commands are removed from `tests/fixtures/dry_run_gaps.json`.
The ratchet invariant test confirms that no OpenTofu command remains unclassified.
MCP tool definitions in `CONST_MCP_EXPOSURE_TABLE` match the read-only hints.

## Error Handling

Plan builders catch only expected errors such as `OSError` and `ValueError`.
Plan builders do not catch generic exceptions.
When an invalid directory or option is supplied, the command exits with standard Typer validation errors.
