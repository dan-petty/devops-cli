# devops-cli-dashboard Specification

## Purpose
How the Grafana dashboard `k8s/monitoring/dashboards/devops-cli.json` shows the devops commands and the GitHub API: the golden signals row first, breakdown tables that link to it, and the chart rules that each panel follows.

## Requirements

### Requirement: The devops-cli dashboard opens with the golden signals of the devops commands
The first row of `devops-cli.json` SHALL be "Golden signals: devops commands", with four time series of `w12 h8`, two to a line, in the order latency (`s`), traffic (`short`), errors (`percentunit`) and saturation (`percentunit`). Traffic, errors and saturation SHALL start their y axis at 0.

#### Scenario: The first row is read
- **WHEN** a test reads the panels of `devops-cli.json`
- **THEN** the first panel is the row "Golden signals: devops commands"
- **AND** its panels have the titles that start with "Latency", "Traffic", "Errors" and "Saturation", the units `s`, `short`, `percentunit` and `percentunit`, and the positions (0, 1), (12, 1), (0, 9) and (12, 9)

### Requirement: The golden signals read the sub-command histogram of the selection
Latency, traffic and errors SHALL read `devops_cli_subcommand_duration_seconds` filtered by `$job`, `$command` and `$sub_command`. Latency SHALL show the p50, p95 and p99 of the calls with `status="ok"`. Traffic SHALL show the calls of each hour as bars with a Min interval of 1h. Errors SHALL show the share of the calls with `status="error"`, and 0 for a selection with calls and no error.

#### Scenario: The error share of 100 calls with 7 errors
- **WHEN** promtool evaluates the errors query on fixture series that add 93 ok calls and 7 error calls each 15 min
- **THEN** the query gives 0.07

#### Scenario: The latency of the successful calls
- **WHEN** promtool evaluates the p95 query on fixture series with the ok calls from 1 to 2 s and the error calls from 64 to 128 s
- **THEN** the query gives 2^0.95 s, the p95 of the ok calls only

#### Scenario: The hourly traffic bars
- **WHEN** promtool adds up the traffic bars of 24 h on fixture series with a zero sample and 100 calls each 15 min
- **THEN** the sum is 9,600, the calls of the series in the range

### Requirement: The saturation signal shows the Service GitHub budget
The saturation panel SHALL divide `devops_cli_service_budget_spent_requests` by `devops_cli_service_budget_limit_requests`, with the constant reference line `vector(1)` drawn as a 1 px dashed line.

#### Scenario: The spend of 3,000 requests of a limit of 4,000
- **WHEN** promtool evaluates the saturation query on fixture gauges with the last spend 3,000 and the limit 4,000
- **THEN** the query gives 0.75

### Requirement: The breakdown tables of the devops-cli dashboard link to the golden signals
The row "Breakdown by command" SHALL hold a sorted bar gauge of the calls of each command, and a table of each command with the columns Calls, Errors, Error share, p50, p95 and p99 over `$__range`. The row "Sub-commands" SHALL hold the same table for each sub-command. Each table SHALL be sorted by Errors, then by Calls, and a row SHALL link to the dashboard with `var-command`, and `var-sub_command` for a sub-command, set to the row.

#### Scenario: The tables are read
- **WHEN** a test reads the tables of the two rows
- **THEN** the last transformation of each sorts by Errors, then by Calls, both descending
- **AND** the link of the command table ends with `&var-command=${__data.fields.command}`, and the link of the sub-command table ends with `&var-sub_command=${__data.fields.sub_command:percentencode}`

#### Scenario: A command with no error series
- **WHEN** promtool evaluates the errors and the error share columns on fixture series where ci sends no error series
- **THEN** ci shows 0 errors and an error share of 0

### Requirement: Each panel outside the Service rows has one unit and one axis
Each panel of `devops-cli.json` outside the rows "AI Spend & Economics", "Planner Tools", "Roadmap Service", "Alternatives Check" and "Roadmap Job Success" that is not a table SHALL have targets of one unit and no field override of `unit` or `custom.axisPlacement`. A panel with the unit `s` or `ms` SHALL hold no `histogram_count` target.

#### Scenario: A panel that breaks one rule
- **WHEN** the chart rule test reads a time series with a quantile target and a `histogram_count` target, or with an override that sets `custom.axisPlacement` to `right`
- **THEN** it reports one problem that names the rule

### Requirement: Each panel outside the Service rows names its signal and follows the step
Each panel of `devops-cli.json` outside the Service rows SHALL have a description, a title in the form "Signal: measure", and no repeat. Only a stat SHALL fall back to `or vector(0)`. A time series target SHALL read only the windows `[$__interval]` and `[$__rate_interval]`, and SHALL NOT group by `command` or `sub_command`.

#### Scenario: The shipped dashboard is checked
- **WHEN** the chart rule test reads each panel outside the Service rows
- **THEN** it reports no problem

#### Scenario: The hourly core bars of the Service
- **WHEN** promtool adds up the bars of "GitHub quota: core requests per hour" over 24 h on a fixture counter that starts with a zero sample and adds 30 requests each 15 min
- **THEN** the sum is within 1 % of the 2,880 requests of the counter in the range

### Requirement: The devops-cli dashboard opens on the last day
The dashboard SHALL open on `now-24h` and refresh each minute, because an OTLP series gets about 4 samples an hour.

#### Scenario: The defaults are read
- **WHEN** a test reads the time and the refresh of `devops-cli.json`
- **THEN** they are `now-24h` to `now` and `1m`
