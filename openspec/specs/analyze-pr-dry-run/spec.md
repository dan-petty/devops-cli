# analyze-pr-dry-run Specification

## Purpose
Defines how `devops ai analyze pr` behaves under dry run: it previews the planned action and makes no external call.

## Requirements

### Requirement: Dry run makes no external call
The system SHALL render a dry-run preview for `devops ai analyze pr` and SHALL NOT open a GitHub session, start a child process or write a file when `--dry-run` or the dry-run environment is set.

#### Scenario: Option dry run
- **WHEN** the user runs `devops ai analyze pr 42 --dry-run`
- **THEN** the command prints the dry-run preview, contacts no GitHub service and exits 0

#### Scenario: Environment dry run
- **WHEN** `DEVOPS_CLI_DRY_RUN` is true and the user runs `devops ai analyze pr 42`
- **THEN** the command prints the dry-run preview, contacts no GitHub service and exits 0
