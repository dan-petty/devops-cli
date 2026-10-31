# Proposal: Classify OpenTofu Commands and Add Request Plans in Dry Run

## Why

Issue #2248 classified review commands.
Issue #2249 tracks OpenTofu and Terraform commands.
Nine commands reach providers, remote backends, or external security tools.
Six commands inspect or format local configuration files.
Some commands print echo-only previews that show only arguments.

This change delivers issue #2249.
It classifies all 15 OpenTofu commands and adds request plans.

## What Changes

1. Decorate OpenTofu commands with their dry-run classes:
   - `request-plan`: `tf init`, `tf plan`, `tf apply`, `tf destroy`, `tf output`, `tf deploy-cloud`, `tf lint`, `tf cost breakdown`, and `tf cost diff`.
   - `no-external-request`: `tf drift`, `tf fmt`, `tf graph`, `tf notify-plan`, `tf status`, and `tf validate`.
2. Create `src/devops_cli/tf/tf_plans.py` to build ordered `PlannedRequest` sequences.
3. Remove echo-only previews and explicit `--dry-run` options from read-only commands without a shim.
4. Remove all 15 OpenTofu command paths from `tests/fixtures/dry_run_gaps.json`.
5. Add unit and invariant test coverage to verify dry-run behavior.

This change fits in one pull request.

## Capabilities

- `command-dry-run-class`: Extend capability with requirements for OpenTofu request plans and local command execution.

## Impact

- All OpenTofu commands obey the dry-run rule.
- External provider, backend, and scanner executions do not occur in dry run.
- Operators inspect planned commands and arguments before execution.

## Feasibility

We confirmed the behavior of all 15 commands in `src/devops_cli/commands/tf.py`.
Commands that execute external processes or network scans are confirmed.
The dry run proxy and `PlannedRequest` architecture support subprocess execution plans.

## Existing Tool Considered

We considered Typer native dry-run support, but Typer does not generate request plans.
`devops_cli.dry_run.requests.PlannedRequest` is the established repository standard.
We delete legacy echo-only logic without adding external dependencies.
