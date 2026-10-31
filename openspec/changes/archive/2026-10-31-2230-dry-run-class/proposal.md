# Proposal

## Why

Issue #2230: The owner dry-run rule states that a dry run makes no external request. External requests include GitHub, Kubernetes clusters, AI models, network endpoints, and child processes that access them. A dry run returns planned requests and the real result type. Commands without external requests can run normally in dry-run mode. Currently, no code records which commands follow this rule, and no invariant test prevents new commands from violating it.

## What Changes

- Add a `@dry_run_class` decorator in `src/devops_cli/dry_run/decorator.py` supporting `request-plan` and `no-external-request` classes.
- Update lazy proxy resolution in `src/devops_cli/core/command_resolver.py` to run `no-external-request` commands normally under `--dry-run`.
- Add `tests/fixtures/dry_run_gaps.json` containing the list of command paths lacking a dry-run class.
- Mark the 32 distinct commands that currently implement request plans with `@dry_run_class("request-plan")`.
- Add `tests/test_dry_run_class_ratchet.py` enforcing that every command reachable from `_COMMAND_SPECS` has a valid class or appears in `dry_run_gaps.json`.
- Add an MCP consistency check ensuring that tools in `CONST_MCP_EXPOSURE_TABLE` wrapping `no-external-request` commands specify `readOnlyHint: true`.
- Remove the obsolete substring test `test_invariants_all_dry_run_commands_consistent` in `tests/test_main_dry_run.py`.

## Capabilities

### New Capabilities

- `command-dry-run-class`: command-declares-dry-run-class, proxy-runs-no-external-request-commands, ratchet-prevents-unclassified-commands, mcp-read-only-hint-agrees-with-no-external-request

### Modified Capabilities

None.

## Impact

Reachable commands with `request-plan` declare `--dry-run`. Reachable commands with `no-external-request` execute normally when `--dry-run` is active. Unclassified commands continue to print the delegated preview message.

## Feasibility

- Premise confirmed: `src/devops_cli/dry_run/decorator.py` exists and wraps command callbacks.
- `_COMMAND_SPECS` in `src/devops_cli/main.py` provides 512 total command paths.
- The 32 existing request-plan callbacks declare `--dry-run` and handle request planning.
- `CONST_MCP_EXPOSURE_TABLE` in `src/devops_cli/config/constants.py` contains 142 tool specifications.
- All new tests avoid sockets, network calls, and subprocess execution, satisfying the test floor.

## Existing Tool Considered

Click and Typer offer command inspection and callback metadata attachment via function attributes. Reusing Python function attributes copied by `functools.wraps` satisfies the requirement without new libraries or overhead.
