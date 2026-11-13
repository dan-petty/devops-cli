## MODIFIED Requirements

### Requirement: devops-cli dashboard includes an error stream panel
The `k8s/devops/dashboards/devops-cli.json` dashboard SHALL include a logs panel that shows the log records of `devops-cli` in Loki at the levels error, critical and fatal, and no warnings.

#### Scenario: Error stream panel is present in the dashboard
- **WHEN** the panels of `devops-cli.json` are read
- **THEN** one panel of type `logs` has the title "Errors: error logs of devops-cli"
- **AND** the panel targets the `loki` datasource with the query `{service_name="devops-cli"} | detected_level=~"error|critical|fatal"`

### Requirement: The devops-cli dashboard filters by job
The dashboard `k8s/devops/dashboards/devops-cli.json` SHALL have the multi-value query variable `job`, with All, as its first variable. It SHALL read its values with `label_values({__name__=~"devops_cli_command_total|devops_cli_github_requests_total"}, job)`. Each Prometheus query of the dashboard SHALL filter each `devops_cli_*` series with the matcher `job=~"$job"` first in its selector.

#### Scenario: The job variable is a query
- **WHEN** the dashboard file is read
- **THEN** the first variable is `job`, a query variable of the Prometheus datasource with Multi-value and All, and it holds no fixed options

#### Scenario: The job variable reads a series that the Service sends as it works
- **WHEN** the query of the variable `job` is read
- **THEN** its selector holds `devops_cli_command_total` and `devops_cli_github_requests_total`

#### Scenario: Each query filters by job
- **WHEN** each Prometheus query of the dashboard file is read
- **THEN** each `devops_cli_*` series in the query has a selector that starts with `job=~"$job"`

### Requirement: The devops-cli dashboard lists each sub-command of its series in one table
The `command` variable of `k8s/devops/dashboards/devops-cli.json` SHALL read its values with `label_values(devops_cli_command_total{job=~"$job"}, command)`. The multi-value variable `sub_command`, with All, SHALL read its values with `label_values(devops_cli_subcommand_duration_seconds{job=~"$job",command=~"$command"}, sub_command)`. The row "Sub-commands" SHALL hold one table and no panel that repeats.

#### Scenario: The variables are queries
- **WHEN** the dashboard file is read
- **THEN** `command` and `sub_command` are query variables of the Prometheus datasource with Multi-value and All, and hold no fixed options

#### Scenario: The sub-command row is one table
- **WHEN** the dashboard file is read
- **THEN** the row "Sub-commands" holds one panel of type `table` with no repeat
- **AND** each query of the table is instant and filters `devops_cli_subcommand_duration_seconds` by `$job`, `$command` and `$sub_command`
