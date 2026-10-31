# command-dry-run-class Specification

## Purpose
Devops-cli commands declare their dry-run behavior so that users and agents know command side effects and run read-only operations safely.

## Requirements

### Requirement: command-declares-dry-run-class
Every command callback in devops-cli SHALL support explicit dry-run classification via the `@dry_run_class` decorator with values `request-plan` or `no-external-request`. A command marked with `request-plan` SHALL declare the `--dry-run` option.

#### Scenario: command declares request-plan class
- **WHEN** a command callback is decorated with `@dry_run_class("request-plan")`
- **THEN** inspecting the callback or Click command reveals the classification attribute `request-plan` and the command exposes `--dry-run`

### Requirement: proxy-runs-no-external-request-commands
When the user executes `devops --dry-run <command>` for a command with the `no-external-request` classification, the lazy proxy SHALL execute the command normally without `--dry-run` if the command does not declare `--dry-run`.

#### Scenario: dry run executes no-external-request command
- **WHEN** the user executes `devops --dry-run <command>` on a command marked `no-external-request`
- **THEN** the command executes without error and prints its normal output

### Requirement: ratchet-prevents-unclassified-commands
Every command path reachable from `_COMMAND_SPECS` SHALL either carry a dry-run classification or be listed in `tests/fixtures/dry_run_gaps.json`. An unclassified command missing from the gap list, or a classified command remaining in the gap list, SHALL fail the ratchet test.

#### Scenario: unclassified command not in gap list fails
- **WHEN** a new command path is added without a dry-run class and without an entry in `dry_run_gaps.json`
- **THEN** the ratchet test fails and identifies the missing command

### Requirement: mcp-read-only-hint-agrees-with-no-external-request
An MCP tool entry in `CONST_MCP_EXPOSURE_TABLE` that delegates to a command marked `no-external-request` SHALL specify `readOnlyHint` as true.

#### Scenario: mcp tool wraps no-external-request command
- **WHEN** an MCP tool definition in `CONST_MCP_EXPOSURE_TABLE` maps to a command path with `no-external-request`
- **THEN** the third element of the table entry is `True`
