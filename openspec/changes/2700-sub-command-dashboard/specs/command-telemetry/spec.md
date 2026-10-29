## ADDED Requirements

### Requirement: The sub-command histogram names the command group and the sub-command
`devops_cli_subcommand_duration_seconds` SHALL hold the command group in the label `command`, the command path below `devops` in the label `sub_command`, and `ok` or `error` in the label `status`. A command with no command group above it SHALL name itself in `command` and `sub_command`.

#### Scenario: A sub-command of a command group
- **WHEN** a person runs `devops <group> set <key> <value>` with telemetry export on
- **THEN** `devops_cli_subcommand_duration_seconds` has one point with the `command` `<group>`, the `sub_command` `<group> set` and the `status` `ok`

#### Scenario: A command with no group
- **WHEN** a command `alone` runs with no command group above it
- **THEN** `devops_cli_subcommand_duration_seconds` has one point with the `command` `alone` and the `sub_command` `alone`

### Requirement: The devops-cli dashboard finds each sub-command from its series
The `command` variable of `k8s/monitoring/dashboards/devops-cli.json` SHALL read its values with `label_values(devops_cli_command_total, command)`. The multi-value variable `sub_command`, with All, SHALL read its values with `label_values(devops_cli_subcommand_duration_seconds{command=~"$command"}, sub_command)`. The row "Sub-commands" SHALL hold the panel "Sub-command Calls" and the panel "Telemetry: $sub_command", which repeats for each selected sub-command.

#### Scenario: The variables are queries
- **WHEN** the dashboard file is read
- **THEN** `command` and `sub_command` are query variables of the Prometheus datasource with Multi-value and All, and hold no fixed options

#### Scenario: The latency panel repeats by sub-command
- **WHEN** the dashboard file is read
- **THEN** the panel "Telemetry: $sub_command" repeats by `sub_command`, four to a line
- **AND** each query of the row filters `devops_cli_subcommand_duration_seconds` by `$command` and `$sub_command`
