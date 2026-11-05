## ADDED Requirements

### Requirement: The devops-cli dashboard filters by job
The dashboard `k8s/monitoring/dashboards/devops-cli.json` SHALL have the multi-value query variable `job`, with All, as its first variable. It SHALL read its values with `label_values(devops_cli_command_total, job)`. Each Prometheus query of the dashboard SHALL filter each `devops_cli_*` series with the matcher `job=~"$job"` first in its selector.

#### Scenario: The job variable is a query
- **WHEN** the dashboard file is read
- **THEN** the first variable is `job`, a query variable of the Prometheus datasource with Multi-value and All, and it holds no fixed options

#### Scenario: Each query filters by job
- **WHEN** each Prometheus query of the dashboard file is read
- **THEN** each `devops_cli_*` series in the query has a selector that starts with `job=~"$job"`

## MODIFIED Requirements

### Requirement: The devops-cli dashboard finds each sub-command from its series
The `command` variable of `k8s/monitoring/dashboards/devops-cli.json` SHALL read its values with `label_values(devops_cli_command_total{job=~"$job"}, command)`. The multi-value variable `sub_command`, with All, SHALL read its values with `label_values(devops_cli_subcommand_duration_seconds{job=~"$job",command=~"$command"}, sub_command)`. The row "Sub-commands" SHALL hold the panel "Sub-command Calls" and the panel "Telemetry: $sub_command", which repeats for each selected sub-command.

#### Scenario: The variables are queries
- **WHEN** the dashboard file is read
- **THEN** `command` and `sub_command` are query variables of the Prometheus datasource with Multi-value and All, and hold no fixed options

#### Scenario: The latency panel repeats by sub-command
- **WHEN** the dashboard file is read
- **THEN** the panel "Telemetry: $sub_command" repeats by `sub_command`, four to a line
- **AND** each query of the row filters `devops_cli_subcommand_duration_seconds` by `$job`, `$command` and `$sub_command`
