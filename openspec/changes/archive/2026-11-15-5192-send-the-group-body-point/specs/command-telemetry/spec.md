## ADDED Requirements

### Requirement: A group body sends the sub-command histogram point
A command group that runs its own body with no sub-command SHALL send one point to `devops_cli_subcommand_duration_seconds`, with the group in `command` and in `sub_command` and `ok` or `error` in `status`. A run with a sub-command SHALL send one point from that sub-command, and the group body SHALL send none.

#### Scenario: A group with no sub-command
- **WHEN** `devops ci` runs its body
- **THEN** the histogram has one point with `command` `ci`, `sub_command` `ci` and `status` `ok`

#### Scenario: A group with a sub-command
- **WHEN** `devops ci test path` runs
- **THEN** the histogram has one point with `command` `ci` and `sub_command` `ci test path`

#### Scenario: A group body that fails
- **WHEN** the body of `devops gh` exits 1
- **THEN** its point holds `status` `error`
